"""Config for the generic lakebase accelerator (infra control plane only).

The accelerator is use-case agnostic: callers pass a use-case *name* (→ an isolated
Terraform workspace) plus a path to that use case's tfvars (and optionally a DAB
bundle dir). No use case is hardcoded here.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
TERRAFORM_DIR = REPO_ROOT / "infra" / "terraform"


@dataclass(frozen=True)
class Settings:
    databricks_host: str = field(default_factory=lambda: os.getenv("DATABRICKS_HOST", ""))
    databricks_token: str = field(default_factory=lambda: os.getenv("DATABRICKS_TOKEN", ""))
    cloud: str = field(default_factory=lambda: os.getenv("CLOUD", "aws"))
    max_workers: int = field(default_factory=lambda: int(os.getenv("MAX_WORKERS", "2")))
    spark_version: str = field(default_factory=lambda: os.getenv("SPARK_VERSION", "15.4.x-scala2.12"))


SETTINGS = Settings()
