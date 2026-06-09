"""Databricks Asset Bundle wrapper — replaces Terraform for all infrastructure.

Generates a per-use-case ``databricks.yml`` with the correct cluster spec
(cloud-specific spot attributes, autoscale vs single-node, custom tags) and
runs ``databricks bundle validate/deploy/destroy`` against it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from accelerator.config import DEFAULT_NODE_TYPES, BUNDLE_DIR, SETTINGS, WORKSPACES_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_node_type(cloud: str, override: str) -> str:
    """Return the node type: explicit override or per-cloud default."""
    if override:
        return override
    return DEFAULT_NODE_TYPES.get(cloud, DEFAULT_NODE_TYPES["aws"])


def _build_cluster_resource(
    usecase: str,
    settings: Any,
    extra_tags: dict[str, str] | None = None,
) -> dict:
    """Build the full cluster resource dict for ``databricks.yml``."""
    if settings.max_workers > 2:
        raise ValueError(f"max_workers must be <= 2 (cost guardrail), got {settings.max_workers}")

    node_type = _resolve_node_type(settings.cloud, settings.node_type_id)

    # Base tags
    tags: dict[str, str] = {
        "project": "lakebase-accelerator",
        "usecase": usecase,
        "managed": "dab",
    }
    tags.update(settings.custom_tags)
    if extra_tags:
        tags.update(extra_tags)

    # Spark conf
    spark_conf: dict[str, str] = {"spark.sql.shuffle.partitions": "8"}
    if settings.single_node:
        spark_conf["spark.databricks.cluster.profile"] = "singleNode"
        spark_conf["spark.master"] = "local[*]"
        tags["ResourceClass"] = "SingleNode"

    cluster: dict[str, Any] = {
        "cluster_name": f"lakebase-{usecase}-cluster",
        "spark_version": settings.spark_version,
        "node_type_id": node_type,
        "autotermination_minutes": settings.autotermination_minutes,
        "data_security_mode": "SINGLE_USER",
        "spark_conf": spark_conf,
        "custom_tags": tags,
    }

    # Workers: single-node (driver only) or autoscale
    if settings.single_node:
        cluster["num_workers"] = 0
    else:
        cluster["autoscale"] = {
            "min_workers": settings.min_workers,
            "max_workers": settings.max_workers,
        }

    # Cloud-specific spot / preemptible attributes
    if settings.use_spot:
        if settings.cloud == "azure":
            cluster["azure_attributes"] = {
                "availability": "SPOT_WITH_FALLBACK_AZURE",
                "first_on_demand": 1,
                "spot_bid_max_price": -1,
            }
        elif settings.cloud == "aws":
            cluster["aws_attributes"] = {
                "availability": "SPOT_WITH_FALLBACK",
                "first_on_demand": 1,
                "spot_bid_price_percent": 100,
            }
        elif settings.cloud == "gcp":
            cluster["gcp_attributes"] = {
                "availability": "PREEMPTIBLE_WITH_FALLBACK_GCP",
            }

    return cluster


def _build_schema_resource(usecase: str, settings: Any) -> dict | None:
    """Build the UC schema resource dict, or None if disabled."""
    if not settings.create_schema:
        return None
    return {
        "catalog_name": settings.catalog_name,
        "name": f"lakebase_{usecase}",
        "comment": f"Use-case schema managed by lakebase accelerator ({usecase}).",
    }


def _render_bundle_yaml(
    usecase: str,
    settings: Any,
    target: str = "dev",
    extra_tags: dict[str, str] | None = None,
) -> Path:
    """Generate a fully-resolved ``databricks.yml`` in the use-case workspace dir."""
    ws_dir = WORKSPACES_DIR / usecase
    ws_dir.mkdir(parents=True, exist_ok=True)

    cluster = _build_cluster_resource(usecase, settings, extra_tags)

    resources: dict[str, Any] = {
        "clusters": {"lakebase_cluster": cluster},
    }
    schema = _build_schema_resource(usecase, settings)
    if schema:
        resources["schemas"] = {"lakebase_schema": schema}

    bundle_doc: dict[str, Any] = {
        "bundle": {"name": f"lakebase-{usecase}"},
        "targets": {
            target: {
                "default": True,
                "mode": "development" if target != "prod" else "production",
            },
        },
        "resources": resources,
    }

    out = ws_dir / "databricks.yml"
    out.write_text(yaml.dump(bundle_doc, default_flow_style=False, sort_keys=False))
    return ws_dir


# ---------------------------------------------------------------------------
# CLI wrappers
# ---------------------------------------------------------------------------

def _available() -> bool:
    return shutil.which("databricks") is not None


def _env() -> dict[str, str]:
    env = os.environ.copy()
    # Only inject credentials if explicitly configured — otherwise let the
    # databricks CLI fall back to its own profile-based auth.
    if SETTINGS.databricks_host:
        env.setdefault("DATABRICKS_HOST", SETTINGS.databricks_host)
    if SETTINGS.databricks_token:
        env.setdefault("DATABRICKS_TOKEN", SETTINGS.databricks_token)
    # DAB uses Terraform internally; point it at the local binary to avoid
    # download issues (expired GPG keys, network restrictions).
    tf_path = shutil.which("terraform")
    if tf_path:
        env.setdefault("DATABRICKS_TF_EXEC_PATH", tf_path)
        # Read the installed version so DAB doesn't reject a version mismatch.
        try:
            ver = subprocess.run(
                [tf_path, "version", "-json"], capture_output=True, text=True
            )
            if ver.returncode == 0:
                env.setdefault(
                    "DATABRICKS_TF_VERSION",
                    json.loads(ver.stdout)["terraform_version"],
                )
        except Exception:
            pass
    return env


def _run(args: list[str], cwd: str | Path, check: bool = True) -> subprocess.CompletedProcess:
    if not _available():
        print("  ! databricks CLI not found — install: https://docs.databricks.com/en/dev-tools/cli/install.html")
        raise FileNotFoundError("databricks CLI not found")
    print(f"  $ databricks {' '.join(args)}")
    return subprocess.run(
        ["databricks", *args], cwd=cwd, env=_env(), check=check, text=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _merge_settings(settings: Any, var_overrides: dict[str, Any] | None) -> Any:
    """Return a new Settings with var_overrides applied on top."""
    if not var_overrides:
        return settings
    from dataclasses import fields as dc_fields, asdict
    from accelerator.config import Settings, _parse_tags

    base = asdict(settings)
    for k, v in var_overrides.items():
        if k == "custom_tags" and isinstance(v, str):
            v = _parse_tags(v)
        if k in base:
            # Coerce types to match the field
            expected = type(base[k])
            if expected is bool and isinstance(v, str):
                v = v.lower() in ("true", "1", "yes")
            elif expected is int and isinstance(v, str):
                v = int(v)
            base[k] = v
    return Settings(**base)


def validate(
    usecase: str,
    target: str = "dev",
    var_overrides: dict[str, Any] | None = None,
    extra_tags: dict[str, str] | None = None,
) -> None:
    """Render the bundle YAML and run ``databricks bundle validate``."""
    merged = _merge_settings(SETTINGS, var_overrides)
    ws_dir = _render_bundle_yaml(usecase, merged, target, extra_tags)
    _run(["bundle", "validate", "-t", target], cwd=ws_dir)
    print("[validate] ok.")


def deploy(
    usecase: str,
    target: str = "dev",
    var_overrides: dict[str, Any] | None = None,
    extra_tags: dict[str, str] | None = None,
) -> str:
    """Deploy the use-case infra. Returns the cluster id (or empty string)."""
    merged = _merge_settings(SETTINGS, var_overrides)
    ws_dir = _render_bundle_yaml(usecase, merged, target, extra_tags)
    print(f"[deploy] spinning up infra for {usecase} ...")
    _run(["bundle", "deploy", "-t", target], cwd=ws_dir)

    # Try to extract cluster id from bundle summary
    cluster_id = _get_cluster_id(usecase, target, ws_dir)
    print(f"[deploy] done. cluster_id={cluster_id or '(pending — check Databricks UI)'}")
    print(f"[deploy] run `lakebase destroy {usecase}` when finished to stop billing.")
    return cluster_id


def destroy(usecase: str, target: str = "dev") -> None:
    """Tear down use-case infra (stops billing)."""
    ws_dir = WORKSPACES_DIR / usecase
    if not (ws_dir / "databricks.yml").exists():
        print(f"[destroy] no deployment state found for '{usecase}' — nothing to destroy.")
        return
    print(f"[destroy] tearing down {usecase} ...")
    _run(["bundle", "destroy", "-t", target, "--auto-approve"], cwd=ws_dir)
    print("[destroy] done.")


def status(usecase: str, target: str = "dev") -> dict[str, str]:
    """Get deployment status for a use case."""
    ws_dir = WORKSPACES_DIR / usecase
    if not (ws_dir / "databricks.yml").exists():
        return {"state": "not_deployed"}
    res = subprocess.run(
        ["databricks", "bundle", "summary", "-t", target, "--output", "json"],
        cwd=ws_dir, env=_env(), capture_output=True, text=True,
    )
    if res.returncode != 0:
        return {"state": "unknown", "error": res.stderr.strip()}
    try:
        data = json.loads(res.stdout)
        return {"state": "deployed", "summary": data}
    except json.JSONDecodeError:
        return {"state": "deployed", "raw": res.stdout.strip()}


def list_deployments() -> list[str]:
    """List all use-case names that have local deployment state."""
    if not WORKSPACES_DIR.exists():
        return []
    return sorted(
        d.name for d in WORKSPACES_DIR.iterdir()
        if d.is_dir() and (d / "databricks.yml").exists()
    )


def _get_cluster_id(usecase: str, target: str, ws_dir: Path) -> str:
    """Try to extract the cluster id from the bundle summary."""
    res = subprocess.run(
        ["databricks", "bundle", "summary", "-t", target, "--output", "json"],
        cwd=ws_dir, env=_env(), capture_output=True, text=True,
    )
    if res.returncode != 0:
        return ""
    try:
        data = json.loads(res.stdout)
        # Navigate the summary to find cluster id
        resources = data.get("resource_status", data.get("resources", {}))
        if isinstance(resources, dict):
            clusters = resources.get("clusters", {})
            for name, info in clusters.items():
                cid = info.get("id", info.get("cluster_id", ""))
                if cid:
                    return cid
    except (json.JSONDecodeError, AttributeError):
        pass
    return ""
