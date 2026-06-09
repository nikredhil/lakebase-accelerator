"""Lakebase Accelerator — reusable, use-case-agnostic Databricks IaC control plane.

Provisions cost-tuned Databricks clusters (spot workers, autoscale 1-2 nodes,
autotermination) via Databricks Asset Bundles.  Each use case gets its own
isolated deployment — no hardcoded use cases here.

Quick start::

    from accelerator import plan, deploy, destroy, status

    deploy("code_migration")
    destroy("code_migration")

CLI::

    lakebase plan    <name> [--target dev] [--var k=v] [--tags k=v]
    lakebase deploy  <name> [--target dev] [--var k=v] [--tags k=v]
    lakebase destroy <name>
    lakebase status  <name>
    lakebase list

Submodules:
    cli     — argparse CLI + importable plan/deploy/destroy/status functions
    config  — Settings dataclass (from env/.env), path constants
    dab     — DAB wrapper: renders per-use-case databricks.yml, runs bundle CLI
"""

__version__ = "0.3.0"

__all__ = ["deploy", "destroy", "plan", "status", "__version__"]


def __getattr__(name):
    if name in ("deploy", "destroy", "plan", "status"):
        from accelerator import cli

        return getattr(cli, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
