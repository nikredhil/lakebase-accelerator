"""Thin Python wrapper around the Terraform CLI.

Each use case gets its own Terraform *workspace* (state), so infra is use-case
specific and `destroy` only tears down that use case — never another's.
"""
from __future__ import annotations

import subprocess
from typing import Optional

from accelerator.config import SETTINGS, TERRAFORM_DIR, UseCase


def _env() -> dict:
    """Terraform reads TF_VAR_* for provider auth + sizing (no secrets on CLI)."""
    import os

    env = os.environ.copy()
    env.setdefault("TF_VAR_databricks_host", SETTINGS.databricks_host)
    env.setdefault("TF_VAR_databricks_token", SETTINGS.databricks_token)
    env.setdefault("TF_VAR_cloud", SETTINGS.cloud)
    env.setdefault("TF_VAR_max_workers", str(SETTINGS.max_workers))
    env.setdefault("TF_VAR_spark_version", SETTINGS.spark_version)
    env.setdefault("TF_IN_AUTOMATION", "1")
    return env


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"  $ terraform {' '.join(args)}")
    return subprocess.run(
        ["terraform", *args], cwd=TERRAFORM_DIR, env=_env(), check=check, text=True
    )


def _select_workspace(usecase: str) -> None:
    # Create-or-select a per-use-case workspace for isolated state.
    res = subprocess.run(
        ["terraform", "workspace", "select", usecase],
        cwd=TERRAFORM_DIR, env=_env(), text=True, capture_output=True,
    )
    if res.returncode != 0:
        _run(["workspace", "new", usecase])


def init() -> None:
    _run(["init", "-input=false"])


def _var_args(uc: UseCase) -> list[str]:
    return [f"-var-file={uc.tfvars}", "-input=false"]


def plan(uc: UseCase) -> None:
    init()
    _select_workspace(uc.name)
    _run(["validate"])
    _run(["plan", *_var_args(uc)])


def apply(uc: UseCase) -> None:
    init()
    _select_workspace(uc.name)
    _run(["apply", "-auto-approve", *_var_args(uc)])


def destroy(uc: UseCase) -> None:
    init()
    _select_workspace(uc.name)
    _run(["destroy", "-auto-approve", *_var_args(uc)])


def output(name: str, uc: Optional[UseCase] = None) -> str:
    if uc is not None:
        _select_workspace(uc.name)
    res = subprocess.run(
        ["terraform", "output", "-raw", name],
        cwd=TERRAFORM_DIR, env=_env(), text=True, capture_output=True,
    )
    return res.stdout.strip() if res.returncode == 0 else ""
