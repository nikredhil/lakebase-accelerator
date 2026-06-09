"""Lakebase accelerator: reusable, use-case-specific Databricks infra-as-code.

Spin infra + assets up and tear them down with a few function calls:

    from accelerator import deploy, destroy, plan
    deploy("code_migration")   # terraform apply + bundle deploy
    destroy("code_migration")  # bundle destroy + terraform destroy  (stops billing)
"""
__all__ = ["deploy", "destroy", "plan"]


def __getattr__(name):
    # Lazy import so `python -m accelerator.cli` doesn't re-import cli via the package.
    if name in __all__:
        from accelerator import cli

        return getattr(cli, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
