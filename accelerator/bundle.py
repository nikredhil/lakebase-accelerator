"""Thin Python wrapper around the Databricks CLI bundle (DAB) commands.

Deploys/destroys the use-case *assets* (jobs, notebooks) onto the Terraform infra.
The cluster id from Terraform is injected as a bundle variable so the job reuses
the provisioned 1-2 node cluster.
"""
from __future__ import annotations

import shutil
import subprocess

from accelerator.config import BUNDLE_DIR, SETTINGS, UseCase


def _available() -> bool:
    return shutil.which("databricks") is not None


def _env() -> dict:
    import os

    env = os.environ.copy()
    env.setdefault("DATABRICKS_HOST", SETTINGS.databricks_host)
    env.setdefault("DATABRICKS_TOKEN", SETTINGS.databricks_token)
    return env


def _run(args: list[str], cluster_id: str = "") -> None:
    if not _available():
        print("  ! databricks CLI not found — skipping bundle step. "
              "Install: https://docs.databricks.com/en/dev-tools/cli/install.html")
        return
    if cluster_id:
        args = [*args, "--var", f"existing_cluster_id={cluster_id}"]
    print(f"  $ databricks {' '.join(args)}")
    subprocess.run(["databricks", *args], cwd=BUNDLE_DIR, env=_env(), check=True, text=True)


def validate(uc: UseCase) -> None:
    if uc.dab_enabled:
        _run(["bundle", "validate", "-t", uc.bundle_target])


def deploy(uc: UseCase, cluster_id: str = "") -> None:
    if uc.dab_enabled:
        _run(["bundle", "deploy", "-t", uc.bundle_target], cluster_id=cluster_id)


def destroy(uc: UseCase) -> None:
    if uc.dab_enabled:
        _run(["bundle", "destroy", "-t", uc.bundle_target, "--auto-approve"])
