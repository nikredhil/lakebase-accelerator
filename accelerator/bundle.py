"""Thin Databricks Asset Bundle (DAB) wrapper. The bundle dir is supplied by the
caller (it lives in the consuming tool's repo); the accelerator just runs the CLI
against it and injects the Terraform cluster id."""
from __future__ import annotations

import os
import shutil
import subprocess

from accelerator.config import SETTINGS


def _available() -> bool:
    return shutil.which("databricks") is not None


def _env() -> dict:
    env = os.environ.copy()
    env.setdefault("DATABRICKS_HOST", SETTINGS.databricks_host)
    env.setdefault("DATABRICKS_TOKEN", SETTINGS.databricks_token)
    return env


def _run(args: list[str], bundle_dir: str, cluster_id: str = "") -> None:
    if not _available():
        print("  ! databricks CLI not found — skipping bundle step. "
              "Install: https://docs.databricks.com/en/dev-tools/cli/install.html")
        return
    if cluster_id:
        args = [*args, "--var", f"existing_cluster_id={cluster_id}"]
    print(f"  $ (cd {bundle_dir}) databricks {' '.join(args)}")
    subprocess.run(["databricks", *args], cwd=bundle_dir, env=_env(), check=True, text=True)


def validate(bundle_dir: str, target: str = "dev") -> None:
    if bundle_dir:
        _run(["bundle", "validate", "-t", target], bundle_dir)


def deploy(bundle_dir: str, target: str = "dev", cluster_id: str = "") -> None:
    if bundle_dir:
        _run(["bundle", "deploy", "-t", target], bundle_dir, cluster_id=cluster_id)


def destroy(bundle_dir: str, target: str = "dev") -> None:
    if bundle_dir:
        _run(["bundle", "destroy", "-t", target, "--auto-approve"], bundle_dir)
