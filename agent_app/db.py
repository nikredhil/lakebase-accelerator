"""Lakebase Postgres connectivity for the in-app agent.

Connects to a deployed Lakebase instance as the app's service principal using a
short-lived OAuth credential minted by the SDK, applies the vendored schema
modules, and exposes a thin query helper. Everything here is best-effort and
import-safe: psycopg is imported lazily so the rest of the app boots even if the
wheel is missing, and callers wrap failures into a graceful "agent unavailable".
"""
from __future__ import annotations

import threading
import time
from typing import Any

from databricks.sdk import WorkspaceClient

import blueprints

DEFAULT_DB = "databricks_postgres"
PORT = 5432
_CRED_TTL_S = 50 * 60  # tokens last ~1h; refresh a little early

# instance_name -> (token, expires_epoch)
_cred_cache: dict[str, tuple[str, float]] = {}
_cred_lock = threading.Lock()


class AgentUnavailable(RuntimeError):
    """Raised when the agent backbone can't be reached (connection/deps/schema)."""


def _require_psycopg():
    try:
        import psycopg  # noqa: F401
        return psycopg
    except Exception as e:  # pragma: no cover - env-dependent
        raise AgentUnavailable(
            "psycopg is not installed in the app runtime; redeploy with the "
            "updated requirements.txt"
        ) from e


def _service_principal_user(w: WorkspaceClient) -> str:
    """The Postgres role name for the caller (SP application id, or user email)."""
    try:
        me = w.current_user.me()
        # Apps run as a service principal: the SCIM record exposes an
        # application id under one of these fields depending on SDK/runtime.
        for attr in ("application_id",):
            val = getattr(me, attr, None)
            if val:
                return val
        return me.user_name
    except Exception:
        return ""


def _token(w: WorkspaceClient, instance_name: str) -> str:
    now = time.time()
    with _cred_lock:
        cached = _cred_cache.get(instance_name)
        if cached and cached[1] > now:
            return cached[0]
    cred = w.database.generate_database_credential(instance_names=[instance_name])
    token = cred.token
    with _cred_lock:
        _cred_cache[instance_name] = (token, now + _CRED_TTL_S)
    return token


def connect(w: WorkspaceClient, instance_name: str, autocommit: bool = True):
    """Open a psycopg connection to the instance's Postgres as the SP."""
    psycopg = _require_psycopg()
    inst = w.database.get_database_instance(instance_name)
    host = inst.read_write_dns
    if not host:
        raise AgentUnavailable(f"instance '{instance_name}' has no endpoint yet")
    user = _service_principal_user(w)
    password = _token(w, instance_name)
    try:
        return psycopg.connect(
            host=host,
            port=PORT,
            dbname=DEFAULT_DB,
            user=user,
            password=password,
            sslmode="require",
            connect_timeout=15,
            autocommit=autocommit,
        )
    except Exception as e:
        raise AgentUnavailable(f"could not connect to {instance_name}: {str(e)[:160]}") from e


def ensure_sp_role(w: WorkspaceClient, instance_name: str) -> None:
    """Register the app SP as a Postgres role on the instance (best-effort)."""
    from databricks.sdk.service.database import (
        DatabaseInstanceRole,
        DatabaseInstanceRoleIdentityType,
        DatabaseInstanceRoleMembershipRole,
    )

    user = _service_principal_user(w)
    if not user:
        return
    try:
        w.database.create_database_instance_role(
            instance_name=instance_name,
            database_instance_role=DatabaseInstanceRole(
                name=user,
                identity_type=DatabaseInstanceRoleIdentityType.SERVICE_PRINCIPAL,
                membership_role=DatabaseInstanceRoleMembershipRole.DATABRICKS_SUPERUSER,
            ),
        )
    except Exception:
        pass  # already exists or insufficient rights — connection will reveal real issues


def apply_schema(w: WorkspaceClient, instance_name: str) -> dict[str, Any]:
    """Apply vendored meta+core+agent SQL, then LangGraph checkpointer setup."""
    ensure_sp_role(w, instance_name)
    modules = blueprints.load_sql_modules()
    applied: list[str] = []
    with connect(w, instance_name) as conn:
        with conn.cursor() as cur:
            for name, sql in modules:
                cur.execute(sql)
                applied.append(name)
        _setup_checkpointer(conn)
    return {"applied": applied, "checkpointer": True}


def _setup_checkpointer(conn) -> None:
    """Create LangGraph's checkpoint* tables (short-term thread state)."""
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except Exception:
        return  # langgraph optional; agent.* still usable for the eval log
    try:
        PostgresSaver(conn).setup()
    except Exception:
        pass


def query(w: WorkspaceClient, instance_name: str, sql: str, params: tuple = ()) -> list[dict]:
    with connect(w, instance_name) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return []
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def agent_ledger(w: WorkspaceClient, instance_name: str, days: int = 30) -> dict:
    """Aggregate the agent.interactions cost ledger (shared by the cost center
    and the agent app). Returns {usd, dbus, breakdown:[...]}.
    """
    rows = query(
        w, instance_name,
        """select branch, agent_version, cast(occurred_at as date) as day,
                  sum(coalesce(cost_usd,0)) as usd,
                  sum(coalesce(prompt_tokens,0) + coalesce(completion_tokens,0)) as tokens,
                  count(*) filter (where role='assistant') as turns
           from agent.interactions
           where occurred_at >= now() - make_interval(days => %s)
           group by branch, agent_version, day
           order by day desc""",
        (int(days),),
    )
    total = 0.0
    breakdown = []
    for r in rows:
        usd = float(r["usd"] or 0)
        total += usd
        breakdown.append({
            "branch": r["branch"],
            "agent_version": r["agent_version"],
            "day": str(r["day"]),
            "usd": round(usd, 6),
            "tokens": int(r["tokens"] or 0),
            "turns": int(r["turns"] or 0),
        })
    return {"usd": round(total, 4), "dbus": None, "breakdown": breakdown}
