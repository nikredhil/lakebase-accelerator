"""Lakebase accelerator control plane — generic, use-case agnostic.

    lakebase plan    <name> --vars <tfvars> [--bundle <dir>]
    lakebase deploy  <name> --vars <tfvars> [--bundle <dir>] [--target dev]
    lakebase destroy <name> --vars <tfvars> [--bundle <dir>] [--target dev]
    lakebase list

A use case (e.g. the code-migration tool) supplies its own tfvars + bundle dir;
the accelerator provisions/destroys the infra and injects the cluster id.

Importable: accelerator.deploy(name, vars_file, bundle_dir=None), .destroy(...), .plan(...).
"""
from __future__ import annotations

import argparse
import sys

from accelerator import bundle, terraform


def plan(name: str, vars_file: str, bundle_dir: str | None = None, target: str = "dev") -> None:
    print(f"[plan] {name}")
    terraform.plan(name, vars_file)
    if bundle_dir:
        bundle.validate(bundle_dir, target)
    print("[plan] done — no infra changed.")


def deploy(name: str, vars_file: str, bundle_dir: str | None = None, target: str = "dev") -> None:
    print(f"[deploy] spinning infra for {name} ...")
    terraform.apply(name, vars_file)
    cluster_id = terraform.output(name, "cluster_id")
    if bundle_dir:
        bundle.deploy(bundle_dir, target, cluster_id=cluster_id)
    print(f"[deploy] done. cluster_id={cluster_id or '(n/a)'}")
    print(f"[deploy] run `lakebase destroy {name} --vars {vars_file}` when finished to stop billing.")


def destroy(name: str, vars_file: str, bundle_dir: str | None = None, target: str = "dev") -> None:
    print(f"[destroy] tearing down {name} (stops billing) ...")
    if bundle_dir:
        bundle.destroy(bundle_dir, target)
    terraform.destroy(name, vars_file)
    print("[destroy] done.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lakebase", description="Lakebase accelerator (generic IaC control plane)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for cmd in ("plan", "deploy", "destroy"):
        sp = sub.add_parser(cmd)
        sp.add_argument("name", help="use-case name (-> isolated Terraform workspace)")
        sp.add_argument("--vars", required=True, help="path to the use case's .tfvars")
        sp.add_argument("--bundle", default=None, help="path to the use case's DAB dir (optional)")
        sp.add_argument("--target", default="dev", help="DAB target (default: dev)")
    sub.add_parser("list")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "list":
        print(terraform.list_workspaces() or "(no terraform state yet)")
    elif args.cmd == "plan":
        plan(args.name, args.vars, args.bundle, args.target)
    elif args.cmd == "deploy":
        deploy(args.name, args.vars, args.bundle, args.target)
    elif args.cmd == "destroy":
        destroy(args.name, args.vars, args.bundle, args.target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
