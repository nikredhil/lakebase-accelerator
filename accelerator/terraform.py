"""Thin Terraform wrapper. Each use-case name gets its own workspace (isolated
state), so destroy only tears down that use case. The tfvars path is supplied by
the caller (typically living in the consuming tool's repo)."""
from __future__ import annotations

import os
import subprocess
from typing import Optional

from accelerator.config import SETTINGS, TERRAFORM_DIR


def _env() -> dict:
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
    return subprocess.run(["terraform", *args], cwd=TERRAFORM_DIR, env=_env(), check=check, text=True)


def _select_workspace(name: str) -> None:
    res = subprocess.run(["terraform", "workspace", "select", name],
                         cwd=TERRAFORM_DIR, env=_env(), text=True, capture_output=True)
    if res.returncode != 0:
        _run(["workspace", "new", name])


def init() -> None:
    _run(["init", "-input=false"])


def _vars(name: str, vars_file: str) -> list[str]:
    return [f"-var=usecase={name}", f"-var-file={vars_file}", "-input=false"]


def plan(name: str, vars_file: str) -> None:
    init(); _select_workspace(name); _run(["validate"]); _run(["plan", *_vars(name, vars_file)])


def apply(name: str, vars_file: str) -> None:
    init(); _select_workspace(name); _run(["apply", "-auto-approve", *_vars(name, vars_file)])


def destroy(name: str, vars_file: str) -> None:
    init(); _select_workspace(name); _run(["destroy", "-auto-approve", *_vars(name, vars_file)])


def output(name: str, key: str) -> str:
    _select_workspace(name)
    res = subprocess.run(["terraform", "output", "-raw", key],
                         cwd=TERRAFORM_DIR, env=_env(), text=True, capture_output=True)
    return res.stdout.strip() if res.returncode == 0 else ""


def list_workspaces() -> Optional[str]:
    init()
    res = subprocess.run(["terraform", "workspace", "list"],
                         cwd=TERRAFORM_DIR, env=_env(), text=True, capture_output=True)
    return res.stdout
