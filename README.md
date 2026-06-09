# Lakebase Accelerator

A **reusable, use-case-specific Databricks infra-as-code accelerator**. A few
function calls (or one button) spin up the infra + service behind a use case, and
a **destroy** tears it all down to stop billing. Built so new use cases plug in
without rebuilding the plumbing.

The first use case, **`code_migration`**, implements the whiteboard flow:

> Use Claude to **detect** a SQL / Spark / dbt snippet → **convert** it to
> Databricks PySpark → **run** it on Databricks → **validate** by running the
> original and the converted code against the same data sample and checking the
> results match → **raise a PR** for human review on pass, **retry** on fail
> (learning a lesson into `SKILLS.md` each time).

```
                ┌──────────────── accelerator (control plane) ────────────────┐
                │  plan / deploy / destroy  (Terraform infra + DAB assets)     │
                └──────────────────────────────┬──────────────────────────────┘
                                               │ provisions (1-2 node cluster, schema)
 source code ──► detect ──► convert ──► run candidate (Databricks) ─┐
 (sql/spark/dbt)  (Claude)   (Claude)                                ├─► compare ─► PR (pass)
                              ▲                 run reference (DuckDB/Spark) ─┘        └► retry+learn (fail)
                              └──────────── SKILLS.md (accumulated heuristics) ────────────┘
```

## Design rules (from the brief)

- **Infra-as-code, reusable:** Terraform provisions infra; Databricks Asset
  Bundle (DAB) deploys assets. Per-use-case Terraform workspaces keep state and
  destroy isolated. Add a use case in `accelerator/config.py:USECASES`.
- **Destroy to stop billing:** `accelerator destroy <usecase>` removes assets +
  infra; clusters also auto-terminate when idle.
- **Small + scalable:** runs on a 1–2 node autoscaling cluster against a small
  data sample, but the converted code is real Spark, so it scales to full data.
- **Self-improving:** `SKILLS.md` is injected into the conversion prompt and
  auto-appended with a lesson on every validation failure — the model reuses
  known gotchas instead of re-deriving them (saves tokens).
- **No fancy UI:** a CLI / importable functions are the interface.

## Layout

```
accelerator/        control plane (deploy/destroy/plan wrapping Terraform + DAB)
infra/terraform/    parametrized IaC: cluster (1-2 nodes), UC schema, outputs
bundle/             Databricks Asset Bundle (the use-case job)
usecases/
  code_migration/   examples/ + data/ + pipeline/ + run.py
SKILLS.md           self-updating conversion heuristics
```

## Quick start

```bash
cp .env.example .env          # fill ANTHROPIC_API_KEY, DATABRICKS_HOST/TOKEN, CLOUD, GITHUB_REPO
make install                  # core deps
make install-spark            # local Spark for dry-run (separate venv from databricks-connect!)

# 1) Offline validation — no workspace, no API key needed
make dryrun                   # generate sample data + run local tests

# 2) Run the full pipeline locally (Claude detect+convert; local Spark; dry-run PR)
make run

# 3) Infra lifecycle against your workspace
make plan                     # terraform validate + plan + bundle validate (no changes)
make deploy                   # spin 1-2 node cluster + deploy the job
make destroy                  # tear down (STOP BILLING)
```

The control plane is also importable (the "few function calls"):

```python
from accelerator import deploy, destroy, plan
deploy("code_migration")      # terraform apply + bundle deploy
destroy("code_migration")     # bundle destroy + terraform destroy
```

## Backends & the pyspark / databricks-connect conflict

The **candidate** (converted) code runs via `CANDIDATE_BACKEND`:

- `local` — local `pyspark` (dry-run; needs Java). Reference SQL/dbt use DuckDB.
- `databricks` — your workspace via **Databricks Connect**.

⚠️ `databricks-connect` ships its own pyspark and **must not** share a venv with
`pyspark`. Use one venv for local dry-run (`pyspark`) and a separate venv for the
live path (`databricks-connect`).

## Testing PR creation

Set `GITHUB_REPO=you/your-repo`, then run the pipeline with `--pr-live` (defaults
to dry-run which only prints the git/gh commands). Uses the `gh` CLI against the
current repo — open it in VS Code with your personal GitHub to watch the PR land.

## Prerequisites

Terraform ≥ 1.5, Databricks CLI (for DAB), `gh` (for PRs), Java 8/11/17 (local
Spark), Python 3.10+. The accelerator degrades gracefully — missing Databricks
CLI skips the bundle step with a note rather than failing.

## Adding a new use case

1. Add a `UseCase(...)` to `accelerator/config.py:USECASES`.
2. Add `infra/terraform/usecases/<name>.tfvars`.
3. (Optional) add assets to `bundle/databricks.yml` and a `usecases/<name>/`.
4. `accelerator deploy <name>` / `accelerator destroy <name>`.
```
