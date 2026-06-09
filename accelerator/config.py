"""Central config + use-case registry for the accelerator.

Everything reads from environment variables (loaded from .env). New use cases are
added by appending to USECASES — the accelerator stays generic and reusable.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # python-dotenv optional at runtime
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
TERRAFORM_DIR = REPO_ROOT / "infra" / "terraform"
BUNDLE_DIR = REPO_ROOT / "bundle"
USECASES_DIR = REPO_ROOT / "usecases"
SKILLS_FILE = REPO_ROOT / "SKILLS.md"


@dataclass(frozen=True)
class UseCase:
    """One reusable accelerator use case (infra + assets + pipeline)."""

    name: str
    tfvars: str                      # var-file under infra/terraform/usecases/
    bundle_target: str = "dev"       # DAB target
    description: str = ""
    dab_enabled: bool = True         # whether this use case deploys a bundle


# --- Use-case registry (add new accelerator use cases here) ---
USECASES: dict[str, UseCase] = {
    "code_migration": UseCase(
        name="code_migration",
        tfvars="usecases/code_migration.tfvars",
        bundle_target="dev",
        description="Detect language, convert SQL/Spark/dbt -> Databricks PySpark, "
        "validate by dual-run on a data sample, then raise a PR.",
    ),
}


def get_usecase(name: str) -> UseCase:
    if name not in USECASES:
        raise KeyError(
            f"Unknown use case {name!r}. Known: {', '.join(USECASES)}. "
            f"Add it to accelerator/config.py:USECASES."
        )
    return USECASES[name]


@dataclass(frozen=True)
class Settings:
    databricks_host: str = field(default_factory=lambda: os.getenv("DATABRICKS_HOST", ""))
    databricks_token: str = field(default_factory=lambda: os.getenv("DATABRICKS_TOKEN", ""))
    cloud: str = field(default_factory=lambda: os.getenv("CLOUD", "aws"))
    max_workers: int = field(default_factory=lambda: int(os.getenv("MAX_WORKERS", "2")))
    spark_version: str = field(default_factory=lambda: os.getenv("SPARK_VERSION", "15.4.x-scala2.12"))
    candidate_backend: str = field(default_factory=lambda: os.getenv("CANDIDATE_BACKEND", "local"))
    # converter provider: "anthropic" (Claude) or "rule" (deterministic, no API spend)
    converter_provider: str = field(default_factory=lambda: os.getenv("CONVERTER_PROVIDER", "anthropic"))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    github_repo: str = field(default_factory=lambda: os.getenv("GITHUB_REPO", ""))
    pr_base_branch: str = field(default_factory=lambda: os.getenv("PR_BASE_BRANCH", "main"))


SETTINGS = Settings()
