"""Accelerator control plane: the 'few function calls / one button' interface.

    accelerator plan    <usecase>   # terraform validate + plan (no changes)
    accelerator deploy  <usecase>   # terraform apply  + bundle deploy   (spin infra + assets)
    accelerator destroy <usecase>   # bundle destroy   + terraform destroy (stops billing)
    accelerator run     <usecase>   # run the use-case pipeline locally
    accelerator list                # list registered use cases

Importable equivalents: accelerator.deploy("code_migration"), .destroy(...), .plan(...).
"""
from __future__ import annotations

import argparse
import importlib
import sys

from accelerator import bundle, terraform
from accelerator.config import USECASES, get_usecase


def plan(usecase: str) -> None:
    uc = get_usecase(usecase)
    print(f"[plan] {uc.name}: {uc.description}")
    terraform.plan(uc)
    bundle.validate(uc)
    print("[plan] done — no infra changed.")


def deploy(usecase: str) -> None:
    uc = get_usecase(usecase)
    print(f"[deploy] spinning infra + assets for {uc.name} ...")
    terraform.apply(uc)
    cluster_id = terraform.output("cluster_id", uc)
    bundle.deploy(uc, cluster_id=cluster_id)
    print(f"[deploy] done. cluster_id={cluster_id or '(n/a)'}")
    print("[deploy] remember: `accelerator destroy %s` when finished to stop billing." % uc.name)


def destroy(usecase: str) -> None:
    uc = get_usecase(usecase)
    print(f"[destroy] tearing down {uc.name} (stops billing) ...")
    bundle.destroy(uc)       # assets first
    terraform.destroy(uc)    # then infra
    print("[destroy] done.")


def run(usecase: str, extra: list[str]) -> None:
    """Invoke the use case's own pipeline entrypoint (usecases/<name>/run.py:main)."""
    uc = get_usecase(usecase)
    mod = importlib.import_module(f"usecases.{uc.name}.run")
    mod.main(extra)


def list_usecases() -> None:
    for uc in USECASES.values():
        print(f"  {uc.name:16s} {uc.description}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="accelerator", description="Lakebase accelerator control plane")
    sub = p.add_subparsers(dest="cmd", required=True)
    for cmd in ("plan", "deploy", "destroy"):
        sp = sub.add_parser(cmd)
        sp.add_argument("usecase")
    sp_run = sub.add_parser("run")
    sp_run.add_argument("usecase")
    sp_run.add_argument("extra", nargs=argparse.REMAINDER, help="args forwarded to the use-case pipeline")
    sub.add_parser("list")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "plan":
        plan(args.usecase)
    elif args.cmd == "deploy":
        deploy(args.usecase)
    elif args.cmd == "destroy":
        destroy(args.usecase)
    elif args.cmd == "run":
        run(args.usecase, args.extra)
    elif args.cmd == "list":
        list_usecases()
    return 0


if __name__ == "__main__":
    sys.exit(main())
