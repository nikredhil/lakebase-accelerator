"""Cost center — DBU→$ attribution for the three buckets the user named:
Agent (model serving / interaction log), App (Databricks Apps compute), and
Lakebase (database instance compute + storage).

Live path: query system.billing.usage ⋈ system.billing.list_prices via a SQL
warehouse, plus the agent.interactions cost ledger inside Lakebase. If anything
is unavailable (no warehouse, missing grants, no data), this module NEVER
raises to the route — it returns a rate-based estimate from pricing.py with a
``source: "estimate"`` flag and a note on what to grant.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import (
    Disposition,
    Format,
    State,
    StatementParameterListItem,
    StatementState,
)

import pricing
import service

GRANT_NOTE = (
    "Showing rate-based estimates. For live billing, grant the app's service "
    "principal SELECT on system.billing and CAN_USE on a SQL warehouse "
    "(see scripts/grant_app_access.py)."
)

# Lakebase states that accrue compute cost (vs STOPPED / DELETING).
_RUNNING_DB_STATES = {"AVAILABLE", "STARTING", "UPDATING", "FAILING_OVER"}


# --------------------------------------------------------------------------- #
# Uptime × published-rate model — the primary live cost source.
# Works without system.billing grants: cost = published $/hr × hours running.
# --------------------------------------------------------------------------- #
def _parse_ts(s: Any) -> datetime | None:
    if not s:
        return None
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _hours_since(ts: Any) -> float:
    t = _parse_ts(ts)
    if not t:
        return 0.0
    return max(0.0, (datetime.now(timezone.utc) - t).total_seconds() / 3600.0)


def _cu(capacity: str) -> int:
    try:
        return int(str(capacity).replace("CU_", "")) or 1
    except Exception:
        return 1


def uptime_costs(w: WorkspaceClient, agent_costs: dict | None = None) -> dict:
    """Live cost-to-date for every managed resource, from uptime × published
    rate. Returns the same shape as get_costs (buckets + breakdown)."""
    breakdown: list[dict] = []
    buckets = {b: {"usd": 0.0, "dbus": None} for b in ("agent", "app", "lakebase")}

    # --- Lakebase instances ---
    try:
        for i in service.managed_instances(w):
            tags = service._tags_dict(i)
            state = i.state.value if i.state else "UNKNOWN"
            cu = _cu(i.effective_capacity or i.capacity or "CU_1")
            rate = pricing.lakebase_usd_per_hour(cu)
            running = state in _RUNNING_DB_STATES
            uptime = _hours_since(i.creation_time) if running else 0.0
            usd = pricing.cost_to_date(rate, uptime)
            buckets["lakebase"]["usd"] += usd
            breakdown.append({
                "resource": i.name,
                "bucket": "lakebase",
                "cost_center": tags.get("cost_center") or tags.get("x_cost_center") or "untagged",
                "use_case": tags.get("use_case") or tags.get("usecase") or i.name,
                "state": state,
                "rate_per_hour": rate,
                "uptime_hours": round(uptime, 2),
                "detail": f"{cu} CU · {pricing.LAKEBASE_DBU_PER_CU_HOUR}×{cu} DBU/hr",
                "usd": usd,
            })
    except Exception:
        pass

    # --- The control-plane app itself ---
    try:
        a = w.apps.get(pricing.APP_NAME)
        size = a.compute_size.value if getattr(a, "compute_size", None) else "MEDIUM"
        active = bool(a.compute_status and a.compute_status.state and "ACTIVE" in str(a.compute_status.state))
        rate = pricing.apps_usd_per_hour(size)
        uptime = _hours_since(a.create_time) if active else 0.0
        usd = pricing.cost_to_date(rate, uptime)
        buckets["app"]["usd"] += usd
        breakdown.append({
            "resource": pricing.APP_NAME,
            "bucket": "app",
            "cost_center": "platform",
            "use_case": "control-plane",
            "state": "ACTIVE" if active else "STOPPED",
            "rate_per_hour": rate,
            "uptime_hours": round(uptime, 2),
            "detail": f"Apps {size} · {pricing.APPS_DBU_PER_HOUR.get(size,0.5)} DBU/hr",
            "usd": usd,
        })
    except Exception:
        pass

    # --- Agent: measured per-turn from the co-located interaction ledger ---
    if agent_costs:
        usd = round(float(agent_costs.get("usd") or 0), 4)
        buckets["agent"]["usd"] = usd
        for r in agent_costs.get("breakdown", []):
            breakdown.append({
                "resource": f"agent/{r.get('branch','main')}",
                "bucket": "agent",
                "cost_center": "ml-platform",
                "use_case": "stateful-agent-backbone",
                "state": r.get("agent_version", ""),
                "rate_per_hour": None,
                "uptime_hours": None,
                "detail": f"{r.get('turns',0)} turns · {r.get('tokens',0)} tok",
                "usd": round(float(r.get("usd") or 0), 6),
            })

    for b in buckets.values():
        b["usd"] = round(b["usd"], 4)
        b["basis"] = "uptime × published rate"
    buckets["agent"]["basis"] = "agent.interactions (measured per turn)"

    measured_monthly = _project_from_breakdown(breakdown, buckets)
    return {
        "source": "live",
        "model": "uptime",
        "note": (
            "Cost-to-date = published DBU rate × time each resource has been up. "
            f"Compute uses ${pricing.USD_PER_DBU}/DBU; the agent is metered per turn "
            "from agent.interactions."
        ),
        "buckets": buckets,
        "breakdown": breakdown,
        "projection": pricing.projection(),
        "savings": pricing.savings(pricing.DIY_BASELINE, measured_monthly),
    }


def _project_from_breakdown(breakdown: list[dict], buckets: dict) -> float:
    """Monthly run-rate from current resources' hourly rates (for savings)."""
    hourly = sum(float(r["rate_per_hour"]) for r in breakdown if r.get("rate_per_hour"))
    monthly_compute = hourly * pricing.HOURS_PER_MONTH
    # Agent: scale the measured ledger to a monthly figure if present.
    agent_usd = buckets.get("agent", {}).get("usd") or 0
    return round(monthly_compute + agent_usd, 2)

# --------------------------------------------------------------------------- #
# Billing SQL — App + Lakebase buckets, granular by cost_center × use_case × day
# --------------------------------------------------------------------------- #
_BILLING_SQL = """
WITH priced AS (
  SELECT
    u.usage_date,
    u.usage_quantity AS dbus,
    u.usage_quantity * p.pricing.effective_list.default AS usd,
    COALESCE(u.custom_tags['cost_center'], u.custom_tags['x_cost_center'], 'untagged') AS cost_center,
    COALESCE(u.custom_tags['use_case'], u.custom_tags['usecase'], 'unattributed') AS use_case,
    CASE
      WHEN u.billing_origin_product = 'LAKEBASE'
        OR u.product_features.lakebase IS NOT NULL
        OR u.usage_metadata.database_instance_id IS NOT NULL THEN 'lakebase'
      WHEN u.usage_metadata.app_name = :app_name
        OR u.billing_origin_product = 'APPS' THEN 'app'
      WHEN u.billing_origin_product IN ('MODEL_SERVING', 'SERVING')
        OR lower(u.sku_name) LIKE '%serving%'
        OR lower(u.sku_name) LIKE '%inference%' THEN 'agent'
      ELSE 'other'
    END AS bucket
  FROM system.billing.usage u
  LEFT JOIN system.billing.list_prices p
    ON u.sku_name = p.sku_name
   AND u.usage_end_time >= p.price_start_time
   AND (p.price_end_time IS NULL OR u.usage_end_time < p.price_end_time)
  WHERE u.usage_date >= current_date() - make_interval(0, 0, 0, CAST(:days AS INT))
    AND u.usage_unit = 'DBU'
)
SELECT bucket, cost_center, use_case, CAST(usage_date AS STRING) AS usage_date,
       SUM(dbus) AS dbus, SUM(COALESCE(usd, 0)) AS usd
FROM priced
WHERE bucket <> 'other'
GROUP BY bucket, cost_center, use_case, usage_date
ORDER BY usage_date DESC, bucket
"""


# --------------------------------------------------------------------------- #
# Warehouse discovery + statement execution
# --------------------------------------------------------------------------- #
def pick_warehouse(w: WorkspaceClient) -> str | None:
    """Pick a warehouse for billing queries, in priority order:
    running serverless → any serverless → any running → any → hint.
    """
    try:
        whs = list(w.warehouses.list())
    except Exception:
        return pricing.WAREHOUSE_ID_HINT
    serverless = [x for x in whs if getattr(x, "enable_serverless_compute", False)]
    running_serverless = [x for x in serverless if x.state == State.RUNNING]
    running_any = [x for x in whs if x.state == State.RUNNING]
    for pool in (running_serverless, serverless, running_any, whs):
        if pool:
            return pool[0].id
    return pricing.WAREHOUSE_ID_HINT


def run_query(
    w: WorkspaceClient,
    warehouse_id: str,
    sql: str,
    parameters: list[StatementParameterListItem] | None = None,
    timeout_s: int = 50,
) -> list[dict[str, Any]]:
    """Execute SQL and return rows as dicts. Raises on FAILED/timeout."""
    resp = w.statement_execution.execute_statement(
        statement=sql,
        warehouse_id=warehouse_id,
        disposition=Disposition.INLINE,
        format=Format.JSON_ARRAY,
        parameters=parameters,
        wait_timeout="30s",
    )
    deadline = time.time() + timeout_s
    while resp.status and resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if time.time() > deadline:
            raise TimeoutError("statement execution timed out")
        time.sleep(2)
        resp = w.statement_execution.get_statement(resp.statement_id)

    state = resp.status.state if resp.status else None
    if state != StatementState.SUCCEEDED:
        msg = ""
        if resp.status and resp.status.error:
            msg = resp.status.error.message or ""
        raise RuntimeError(f"query {state}: {msg}")

    if not resp.result or not resp.manifest:
        return []
    cols = [c.name for c in resp.manifest.schema.columns]
    rows = resp.result.data_array or []
    return [dict(zip(cols, r)) for r in rows]


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def _empty_buckets() -> dict[str, dict[str, float]]:
    return {b: {"dbus": 0.0, "usd": 0.0} for b in ("agent", "app", "lakebase")}


def _rollup(rows: list[dict]) -> dict[str, dict[str, float]]:
    buckets = _empty_buckets()
    for r in rows:
        b = r.get("bucket")
        if b in buckets:
            buckets[b]["dbus"] += float(r.get("dbus") or 0)
            buckets[b]["usd"] += float(r.get("usd") or 0)
    for b in buckets.values():
        b["dbus"] = round(b["dbus"], 2)
        b["usd"] = round(b["usd"], 2)
    return buckets


def get_estimate(params: dict | None = None) -> dict:
    """Pure rate-based view — always succeeds, no SDK calls."""
    proj = pricing.projection(params)
    buckets = {
        "agent": {"usd": proj["agent"], "dbus": None, "basis": "rate estimate"},
        "app": {"usd": proj["app"], "dbus": None, "basis": "rate estimate"},
        "lakebase": {"usd": proj["lakebase"], "dbus": None, "basis": "rate estimate"},
    }
    return {
        "source": "estimate",
        "note": GRANT_NOTE,
        "window_days": 30,
        "buckets": buckets,
        "breakdown": [],
        "projection": proj,
        "savings": proj["savings"],
    }


def get_costs(w: WorkspaceClient, days: int = 30, agent_costs: dict | None = None) -> dict:
    """Live cost center.

    Primary source is the uptime × published-rate model (works without billing
    grants): cost-to-date = published $/hr × time each resource has been up.
    Falls back to a pure rate estimate only if even the read-only resource
    listing fails. system.billing is consulted opportunistically to enrich the
    granular breakdown, but is never required.
    """
    try:
        out = uptime_costs(w, agent_costs=agent_costs)
    except Exception as e:
        est = get_estimate()
        est["note"] = f"{GRANT_NOTE} (resource listing unavailable: {str(e)[:120]})"
        if agent_costs:
            _merge_agent_ledger(est, agent_costs)
        return est

    out["window_days"] = int(days)
    # Opportunistic enrichment from system.billing (ignored if not permitted).
    try:
        wh = pick_warehouse(w)
        rows = run_query(
            w, wh, _BILLING_SQL,
            parameters=[
                StatementParameterListItem(name="days", value=str(int(days)), type="INT"),
                StatementParameterListItem(name="app_name", value=pricing.APP_NAME),
            ],
        )
        if rows:
            out["billing_breakdown"] = rows
            out["note"] += " Cross-checked against system.billing."
    except Exception:
        pass
    return out


def _merge_agent_ledger(view: dict, agent_costs: dict) -> None:
    """Overlay the agent.interactions cost ledger onto the Agent bucket."""
    usd = round(float(agent_costs.get("usd") or 0), 4)
    view["buckets"]["agent"] = {
        "usd": usd,
        "dbus": agent_costs.get("dbus"),
        "basis": "agent.interactions (measured per turn)",
    }
    if agent_costs.get("breakdown"):
        view["agent_breakdown"] = agent_costs["breakdown"]


def _monthly_total(buckets: dict, days: int) -> float:
    """Scale the window's measured $ to a monthly figure for the savings model."""
    window_usd = sum(float(v.get("usd") or 0) for v in buckets.values())
    if days <= 0:
        return round(window_usd, 2)
    return round(window_usd / days * 30.0, 2)
