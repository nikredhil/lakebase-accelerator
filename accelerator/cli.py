"""Lakebase accelerator control plane — DAB-based, use-case agnostic.

    lakebase plan    <name> [--target dev] [--var k=v ...] [--vars-file f.json] [--tags k=v,k=v]
    lakebase deploy  <name> [--target dev] [--var k=v ...] [--vars-file f.json] [--tags k=v,k=v]
    lakebase destroy <name> [--target dev]
    lakebase status  <name> [--target dev]
    lakebase list

Importable: ``from accelerator import deploy, destroy, plan, status``.
"""
from __future__ import annotations

import argparse
import json
import sys

from accelerator import dab
from accelerator.config import _parse_tags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_var(s: str) -> tuple[str, str]:
    """Parse ``'key=value'`` into a tuple."""
    if "=" not in s:
        raise argparse.ArgumentTypeError(f"expected key=value, got: {s!r}")
    k, v = s.split("=", 1)
    return k.strip(), v.strip()


def _collect_overrides(args: argparse.Namespace) -> tuple[dict, dict]:
    """Return (var_overrides, extra_tags) from parsed CLI args."""
    var_overrides: dict = {}

    # --vars-file (JSON)
    if getattr(args, "vars_file", None):
        with open(args.vars_file) as f:
            var_overrides.update(json.load(f))

    # --var key=val (repeatable, overrides file)
    for k, v in getattr(args, "var", None) or []:
        var_overrides[k] = v

    # --tags shorthand
    extra_tags: dict[str, str] = {}
    if getattr(args, "tags", None):
        extra_tags = _parse_tags(args.tags)

    return var_overrides, extra_tags


# ---------------------------------------------------------------------------
# Public API (importable from notebooks / scripts)
# ---------------------------------------------------------------------------

def plan(
    name: str,
    target: str = "dev",
    var_overrides: dict | None = None,
    extra_tags: dict[str, str] | None = None,
) -> None:
    print(f"[plan] validating {name} ...")
    dab.validate(name, target, var_overrides, extra_tags)
    print("[plan] done — no infra changed.")


def deploy(
    name: str,
    target: str = "dev",
    var_overrides: dict | None = None,
    extra_tags: dict[str, str] | None = None,
) -> str:
    return dab.deploy(name, target, var_overrides, extra_tags)


def destroy(name: str, target: str = "dev") -> None:
    dab.destroy(name, target)


def status(name: str, target: str = "dev") -> dict:
    return dab.status(name, target)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lakebase",
        description="Lakebase accelerator — DAB-based IaC control plane",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    for cmd in ("plan", "deploy"):
        sp = sub.add_parser(cmd)
        sp.add_argument("name", help="use-case name (isolates resources)")
        sp.add_argument("--target", default="dev", help="DAB target (default: dev)")
        sp.add_argument("--var", type=_parse_var, action="append", metavar="KEY=VAL",
                        help="variable override (repeatable)")
        sp.add_argument("--vars-file", default=None, metavar="PATH",
                        help="JSON file with variable overrides")
        sp.add_argument("--tags", default=None, metavar="K=V,K=V",
                        help="custom tags (team=data,cost_center=1234)")

    sp = sub.add_parser("destroy")
    sp.add_argument("name", help="use-case name to destroy")
    sp.add_argument("--target", default="dev", help="DAB target (default: dev)")

    sp = sub.add_parser("status")
    sp.add_argument("name", help="use-case name to check")
    sp.add_argument("--target", default="dev", help="DAB target (default: dev)")

    sub.add_parser("list")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.cmd == "list":
        deployments = dab.list_deployments()
        if deployments:
            print("Active use-case deployments:")
            for d in deployments:
                print(f"  - {d}")
        else:
            print("(no deployments yet)")

    elif args.cmd == "status":
        info = status(args.name, args.target)
        print(json.dumps(info, indent=2, default=str))

    elif args.cmd in ("plan", "deploy"):
        var_overrides, extra_tags = _collect_overrides(args)
        if args.cmd == "plan":
            plan(args.name, args.target, var_overrides, extra_tags)
        else:
            deploy(args.name, args.target, var_overrides, extra_tags)

    elif args.cmd == "destroy":
        destroy(args.name, args.target)

    return 0


if __name__ == "__main__":
    sys.exit(main())
