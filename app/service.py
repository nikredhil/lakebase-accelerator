"""Lakebase (managed Postgres) provisioning for the Databricks App.

Deploys one **database instance** per use case via the databricks-sdk
Database API. The workspace is the source of truth: managed instances are
discovered by their ``lakebase_project`` custom tag (with a name-prefix
fallback, since some workspaces rename colliding tag keys to ``x_<key>``).

Cost guardrails: capacity capped at CU_2, and instances can be stopped from
the UI (compute billing stops; storage and data remain).
"""
from __future__ import annotations

import re
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import CustomTag, DatabaseInstance

PROJECT_TAG = "lakebase-accelerator"
# Workspaces can enforce default tags; a colliding custom tag key is silently
# renamed to 'x_<key>', so stamp a collision-proof key and accept variants.
PROJECT_TAG_KEY = "lakebase_project"
PROJECT_TAG_KEYS = (PROJECT_TAG_KEY, "x_lakebase_project", "project", "x_project")
NAME_PREFIX = "lakebase-"

ALLOWED_CAPACITIES = ("CU_1", "CU_2")  # cost guardrail — no CU_4/CU_8

USECASE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,30}$")


def detect_cloud(host: str) -> str:
    host = host or ""
    if "azuredatabricks" in host:
        return "azure"
    if "gcp.databricks" in host:
        return "gcp"
    return "aws"


def instance_name(usecase: str) -> str:
    """Instance names must be lowercase alphanumeric/hyphen — slugify."""
    return NAME_PREFIX + usecase.lower().replace("_", "-")


def _tags_dict(instance: DatabaseInstance) -> dict[str, str]:
    tags = instance.effective_custom_tags or instance.custom_tags or []
    return {t.key: t.value for t in tags if t.key}


def _is_managed(instance: DatabaseInstance) -> bool:
    tags = _tags_dict(instance)
    if any(tags.get(k) == PROJECT_TAG for k in PROJECT_TAG_KEYS):
        return True
    return (instance.name or "").startswith(NAME_PREFIX)


def build_instance(usecase: str, opts: dict[str, Any]) -> DatabaseInstance:
    if not USECASE_RE.match(usecase):
        raise ValueError(
            "use-case name must be 1-31 chars: letters, digits, '-' or '_'"
        )
    capacity = opts.get("capacity") or "CU_1"
    if capacity not in ALLOWED_CAPACITIES:
        raise ValueError(
            f"capacity must be one of {ALLOWED_CAPACITIES} (cost guardrail), got {capacity}"
        )

    tags = {
        PROJECT_TAG_KEY: PROJECT_TAG,
        "usecase": usecase,
        "managed": "app",
    }
    tags.update(opts.get("custom_tags") or {})

    kwargs: dict[str, Any] = {
        "name": instance_name(usecase),
        "capacity": capacity,
        "custom_tags": [CustomTag(key=k, value=v) for k, v in tags.items()],
    }
    retention = opts.get("retention_days")
    if retention:
        retention = int(retention)
        if not 2 <= retention <= 35:
            raise ValueError("retention_days must be between 2 and 35")
        kwargs["retention_window_in_days"] = retention

    return DatabaseInstance(**kwargs)


# ---------------------------------------------------------------------------
# Workspace operations
# ---------------------------------------------------------------------------

def managed_instances(w: WorkspaceClient) -> list[DatabaseInstance]:
    return [i for i in w.database.list_database_instances() if _is_managed(i)]


def find_instance(w: WorkspaceClient, usecase: str) -> DatabaseInstance | None:
    target = instance_name(usecase)
    for i in managed_instances(w):
        if _tags_dict(i).get("usecase") == usecase or i.name == target:
            return i
    return None


def to_summary(w: WorkspaceClient, i: DatabaseInstance) -> dict[str, Any]:
    tags = _tags_dict(i)
    name = i.name or ""
    usecase = tags.get("usecase") or name.removeprefix(NAME_PREFIX)
    state = i.state.value if i.state else "UNKNOWN"
    return {
        "usecase": usecase,
        "name": name,
        "state": state,
        "capacity": i.effective_capacity or i.capacity or "?",
        "pg_version": i.pg_version or "",
        "endpoint": i.read_write_dns or "",
        "retention_days": i.effective_retention_window_in_days
        or i.retention_window_in_days,
        "creator": i.creator or "",
        "tags": {
            k: v
            for k, v in tags.items()
            if k not in (*PROJECT_TAG_KEYS, "usecase", "managed")
        },
        "url": f"{w.config.host}/compute/database-instances/{name}",
    }


def deploy(w: WorkspaceClient, usecase: str, opts: dict[str, Any]) -> dict[str, Any]:
    if find_instance(w, usecase):
        raise ValueError(
            f"use case '{usecase}' is already deployed — destroy it first or pick another name"
        )
    instance = build_instance(usecase, opts)
    waiter = w.database.create_database_instance(instance)
    created = waiter.response if waiter.response else None
    return {
        "name": instance.name,
        "state": created.state.value if created and created.state else "STARTING",
    }


def destroy(w: WorkspaceClient, usecase: str) -> dict[str, Any]:
    i = find_instance(w, usecase)
    if not i:
        raise ValueError(f"no deployment found for '{usecase}'")
    # purge: also drop storage so billing fully stops (force is not supported)
    w.database.delete_database_instance(i.name, purge=True)
    return {"destroyed": usecase, "instance": i.name}


def set_stopped(w: WorkspaceClient, name: str, stopped: bool) -> None:
    w.database.update_database_instance(
        name, DatabaseInstance(name=name, stopped=stopped), update_mask="stopped"
    )
