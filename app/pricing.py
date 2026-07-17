"""Pricing model for the Lakebase Accelerator cost center.

SINGLE SOURCE OF TRUTH for every rate/assumption. Edit numbers HERE — never
scatter magic constants across costs.py / agent.py / the UI.

All rates are published Databricks list rates as of mid-2026 (Azure, serverless);
they are conservative defaults and are *overridden at runtime* by the workspace's
own ``system.billing.list_prices`` whenever the live billing query succeeds. The
helpers are pure (no SDK) so they unit-test without credentials.

Sources (captured 2026-06):
  - Databricks Lakebase pricing — autoscaling compute ≈ 0.213 DBU per CU-hour.
    https://www.databricks.com/product/pricing/lakebase
  - Databricks Apps compute — MEDIUM ≈ 0.5 DBU/hr, LARGE ≈ 1.0 DBU/hr.
    https://www.databricks.com/product/pricing  (Apps)
  - Mosaic AI Model Serving — ≈ $0.07 per DBU; Foundation Model APIs are
    pay-per-token, billed as DBUs per 1M tokens (see TOKEN_DBU below).
    https://www.databricks.com/product/pricing/model-serving
"""
from __future__ import annotations

# --------------------------------------------------------------------------- #
# Compute rate multipliers (DBUs consumed per unit of time / work)
# --------------------------------------------------------------------------- #
LAKEBASE_DBU_PER_CU_HOUR = 0.213          # Lakebase autoscaling compute
APPS_DBU_PER_HOUR = {"MEDIUM": 0.5, "LARGE": 1.0}   # Databricks Apps by size
MODEL_SERVING_USD_PER_DBU = 0.07          # Mosaic AI Model Serving $/DBU

# Published $/DBU for serverless compute (Apps + Lakebase). Edit to match your
# workspace's contract; the live system.billing.list_prices query overrides it
# per-SKU when available. ~$0.55 is a representative premium serverless rate.
USD_PER_DBU = 0.55

# Effective $/DBU used ONLY when system.billing.list_prices can't be read.
FALLBACK_USD_PER_DBU = USD_PER_DBU

# Identity / discovery hints (kept here so they're easy to change).
APP_NAME = "lakebase-accelerator"         # used to attribute Apps DBUs in billing
WAREHOUSE_ID_HINT = "c86f5b750db10e6c"    # Serverless Starter Warehouse (fallback)

# --------------------------------------------------------------------------- #
# Foundation Model API token rates — DBUs per 1,000,000 tokens, per model.
# Used to compute agent.interactions.cost_usd at call time (the granular,
# co-located cost ledger). Keyed by the bare model id (serving-endpoint name
# minus the "databricks-" prefix). Unknown models fall back to DEFAULT.
# Source: Databricks Foundation Model APIs pricing table (per 1M tokens).
# --------------------------------------------------------------------------- #
TOKEN_DBU = {
    "claude-opus-4-8":        {"in": 71.429, "out": 357.143},
    "claude-opus-4-5":        {"in": 71.429, "out": 357.143},
    "claude-sonnet-4-5":      {"in": 42.857, "out": 214.286},
    "claude-sonnet-4-6":      {"in": 42.857, "out": 214.286},
    "claude-haiku-4-5":       {"in": 11.429, "out": 57.143},
    "meta-llama-3-3-70b-instruct": {"in": 14.286, "out": 42.857},
    "gpt-oss-120b":           {"in": 10.0,   "out": 30.0},
    "DEFAULT":                {"in": 20.0,   "out": 80.0},
}

# Embedding model (long-term memory recall). DBUs per 1M tokens.
EMBED_MODEL = "databricks-bge-large-en"
EMBED_DBU_PER_M_TOKENS = 0.714

# --------------------------------------------------------------------------- #
# DIY-stack monthly baseline ($/mo) for the "savings vs DIY" model. These are
# editable defaults; the UI lets the user override each line item. They model
# the fragmented stack the flagship narrative calls out: a separate managed
# Postgres + a cache + a vector DB + pipeline compute just to move traces out
# for eval + the ops time to run four systems.
# --------------------------------------------------------------------------- #
DIY_BASELINE = {
    "managed_postgres": 200.0,   # standalone prod Postgres (RDS / Neon)
    "redis_cache":      100.0,   # managed Redis / Elasticache for short-term state
    "vector_db":        150.0,   # managed vector store for memory recall
    "eval_etl_compute": 120.0,   # pipeline compute to ETL traces to the lakehouse
    "ops_overhead":     250.0,   # eng time to operate / glue four systems
}

# Default assumptions for the forward-looking run-rate projection. Overridable
# via query params on /api/costs/estimate.
PROJECTION_DEFAULTS = {
    "cu": 1,                     # Lakebase capacity units
    "lakebase_hours_per_day": 8, # scale-to-zero ⇒ only billed while active
    "apps_size": "MEDIUM",
    "apps_hours_per_day": 24,    # the control-plane app runs continuously
    "agent_in_tokens_per_day": 0,
    "agent_out_tokens_per_day": 0,
    "agent_model": "claude-sonnet-4-5",
}

HOURS_PER_MONTH = 730.0  # 365 * 24 / 12, the standard cloud-billing month


# --------------------------------------------------------------------------- #
# Pure helpers (no SDK — unit-testable without credentials)
# --------------------------------------------------------------------------- #
def dbu_to_usd(dbu: float, usd_per_dbu: float | None = None) -> float:
    return round(float(dbu) * (usd_per_dbu if usd_per_dbu is not None else FALLBACK_USD_PER_DBU), 4)


# --- published hourly rates (DBU/hr × $/DBU) — the basis of the uptime model -- #
def lakebase_usd_per_hour(cu: float, usd_per_dbu: float | None = None) -> float:
    rate = usd_per_dbu if usd_per_dbu is not None else USD_PER_DBU
    return round(LAKEBASE_DBU_PER_CU_HOUR * float(cu) * rate, 6)


def apps_usd_per_hour(size: str, usd_per_dbu: float | None = None) -> float:
    rate = usd_per_dbu if usd_per_dbu is not None else USD_PER_DBU
    dbu = APPS_DBU_PER_HOUR.get((size or "MEDIUM").upper(), APPS_DBU_PER_HOUR["MEDIUM"])
    return round(dbu * rate, 6)


def cost_to_date(usd_per_hour: float, uptime_hours: float) -> float:
    return round(float(usd_per_hour) * max(0.0, float(uptime_hours)), 4)


def _model_key(model: str) -> str:
    """Normalize a serving-endpoint name to a TOKEN_DBU key."""
    key = (model or "").removeprefix("databricks-")
    return key if key in TOKEN_DBU else "DEFAULT"


def token_cost(
    model: str,
    in_tokens: int,
    out_tokens: int,
    usd_per_dbu: float | None = None,
) -> float:
    """USD cost of a single model call from token counts (the per-turn ledger)."""
    rate = TOKEN_DBU[_model_key(model)]
    dbu = (in_tokens / 1_000_000) * rate["in"] + (out_tokens / 1_000_000) * rate["out"]
    price = usd_per_dbu if usd_per_dbu is not None else MODEL_SERVING_USD_PER_DBU
    return round(dbu * price, 6)


def lakebase_monthly_usd(cu: float, hours_per_day: float, usd_per_dbu: float | None = None) -> float:
    dbu_per_month = LAKEBASE_DBU_PER_CU_HOUR * cu * hours_per_day * 30.0
    return dbu_to_usd(dbu_per_month, usd_per_dbu)


def apps_monthly_usd(size: str, hours_per_day: float, usd_per_dbu: float | None = None) -> float:
    rate = APPS_DBU_PER_HOUR.get((size or "MEDIUM").upper(), APPS_DBU_PER_HOUR["MEDIUM"])
    dbu_per_month = rate * hours_per_day * 30.0
    return dbu_to_usd(dbu_per_month, usd_per_dbu)


def model_serving_monthly_usd(
    in_tokens_per_day: int,
    out_tokens_per_day: int,
    model: str = "claude-sonnet-4-5",
    usd_per_dbu: float | None = None,
) -> float:
    daily = token_cost(model, in_tokens_per_day, out_tokens_per_day, usd_per_dbu)
    return round(daily * 30.0, 4)


def savings(diy_items: dict[str, float], lakebase_usd: float) -> dict:
    """DIY monthly total vs the Lakebase-consolidated monthly total."""
    diy_total = round(sum(float(v) for v in (diy_items or {}).values()), 2)
    lakebase_total = round(float(lakebase_usd), 2)
    delta = round(diy_total - lakebase_total, 2)
    pct = round((delta / diy_total * 100.0), 1) if diy_total > 0 else 0.0
    return {
        "diy_total": diy_total,
        "lakebase_total": lakebase_total,
        "delta": delta,
        "pct": pct,
    }


def projection(params: dict | None = None, usd_per_dbu: float | None = None) -> dict:
    """Forward-looking monthly run-rate for the three buckets + savings."""
    p = {**PROJECTION_DEFAULTS, **(params or {})}
    lakebase = lakebase_monthly_usd(p["cu"], p["lakebase_hours_per_day"], usd_per_dbu)
    app = apps_monthly_usd(p["apps_size"], p["apps_hours_per_day"], usd_per_dbu)
    agent = model_serving_monthly_usd(
        p["agent_in_tokens_per_day"], p["agent_out_tokens_per_day"],
        p["agent_model"], usd_per_dbu,
    )
    total = round(lakebase + app + agent, 2)
    return {
        "agent": agent,
        "app": app,
        "lakebase": lakebase,
        "total": total,
        "assumptions": p,
        "savings": savings(DIY_BASELINE, total),
    }
