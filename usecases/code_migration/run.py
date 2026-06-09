"""Entrypoint for the code_migration use case.

Local:        python -m usecases.code_migration.run --example all --backend local
Via control:  accelerator run code_migration -- --example sql
On Databricks: deployed by DAB as a spark_python_task (backend=databricks).
"""
from __future__ import annotations

import argparse
import sys

from usecases.code_migration.config import EXAMPLES
from usecases.code_migration.data import generate_mock_data
from usecases.code_migration.pipeline.orchestrator import run_example


def _parse(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="code_migration")
    p.add_argument("--example", default="all", choices=[*EXAMPLES, "all"])
    p.add_argument("--backend", default=None, choices=["local", "databricks"],
                   help="candidate execution backend (default: CANDIDATE_BACKEND env / local)")
    p.add_argument("--provider", default=None, choices=["anthropic", "rule"],
                   help="conversion provider (default: CONVERTER_PROVIDER env / anthropic). "
                        "'rule' = deterministic, no API spend.")
    p.add_argument("--max-retries", type=int, default=3)
    p.add_argument("--no-pr", action="store_true", help="skip PR creation")
    p.add_argument("--pr-live", action="store_true", help="actually push + open PR (default: dry-run)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    from accelerator.config import SETTINGS

    args = _parse(argv or [])
    backend = args.backend or SETTINGS.candidate_backend
    provider = args.provider or SETTINGS.converter_provider

    print(f"[code_migration] backend={backend} provider={provider}")
    print(f"[code_migration] generating small mock data sample ...")
    generate_mock_data.generate()

    keys = list(EXAMPLES) if args.example == "all" else [args.example]
    results = []
    for key in keys:
        print(f"\n=== {key} ===")
        res = run_example(
            EXAMPLES[key],
            candidate_backend=backend,
            max_retries=args.max_retries,
            raise_pull_request=not args.no_pr,
            pr_dry_run=not args.pr_live,
            provider=provider,
        )
        results.append(res)
        status = "PASS" if res.passed else "FAIL"
        print(f"  detected={res.detected_language} attempts={res.attempts} -> {status}")
        print(f"  {res.detail}")
        if res.lessons:
            print(f"  learned: {res.lessons}")
        if res.pr_detail:
            print(f"  pr: {res.pr_detail}")

    passed = sum(r.passed for r in results)
    print(f"\n[code_migration] {passed}/{len(results)} examples passed validation.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
