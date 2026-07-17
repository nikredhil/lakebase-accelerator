"""Config for the lakebase accelerator (DAB-based infra control plane).

The accelerator is use-case agnostic: callers pass a use-case *name* plus
optional variable overrides. No use case is hardcoded here.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_DIR = REPO_ROOT
WORKSPACES_DIR = REPO_ROOT / ".lakebase"

DEFAULT_NODE_TYPES = {
    "aws": "m5d.large",
    "azure": "Standard_D4s_v3",
    "gcp": "n2-standard-4",
}


def _parse_tags(raw: str) -> dict[str, str]:
    """Parse ``'key=val,key2=val2'`` or JSON ``'{"key":"val"}'`` into a dict."""
    raw = raw.strip()
    if not raw:
        return {}
    if raw.startswith("{"):
        return json.loads(raw)
    tags: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            tags[k.strip()] = v.strip()
    return tags


@dataclass(frozen=True)
class Settings:
    databricks_host: str = field(default_factory=lambda: os.getenv("DATABRICKS_HOST", ""))
    databricks_token: str = field(default_factory=lambda: os.getenv("DATABRICKS_TOKEN", ""))
    cloud: str = field(default_factory=lambda: os.getenv("CLOUD", "aws"))
    max_workers: int = field(default_factory=lambda: int(os.getenv("MAX_WORKERS", "2")))
    min_workers: int = field(default_factory=lambda: int(os.getenv("MIN_WORKERS", "1")))
    spark_version: str = field(default_factory=lambda: os.getenv("SPARK_VERSION", "15.4.x-scala2.12"))
    node_type_id: str = field(default_factory=lambda: os.getenv("NODE_TYPE_ID", ""))
    use_spot: bool = field(default_factory=lambda: os.getenv("USE_SPOT", "true").lower() == "true")
    single_node: bool = field(default_factory=lambda: os.getenv("SINGLE_NODE", "false").lower() == "true")
    autotermination_minutes: int = field(default_factory=lambda: int(os.getenv("AUTOTERMINATION_MINUTES", "20")))
    create_schema: bool = field(default_factory=lambda: os.getenv("CREATE_SCHEMA", "false").lower() == "true")
    catalog_name: str = field(default_factory=lambda: os.getenv("CATALOG_NAME", "main"))
    custom_tags: dict = field(default_factory=lambda: _parse_tags(os.getenv("LAKEBASE_CUSTOM_TAGS", "")))


SETTINGS = Settings()
