# Lakebase Accelerator

A **reusable, use-case-agnostic Databricks infra-as-code control plane**. One
command spins up the infra behind a use case; one tears it down to stop billing.
It owns *infrastructure only* — consuming tools (e.g. the **code-migration-tool**)
plug in by supplying their own `tfvars` and (optional) Databricks Asset Bundle.

```
                ┌──────────── lakebase accelerator (this repo) ────────────┐
  your tool ──► │  lakebase plan|deploy|destroy <name> --vars <tfvars>      │
  (tfvars +     │     Terraform (cluster, schema)  +  DAB (your bundle)     │
   bundle)      └──────────────────────────────────────────────────────────┘
```

## What it provisions
A small, cost-tuned cluster (per-cloud default node type, autoscale **1–2 nodes**,
**spot/preemptible** workers with on-demand fallback, **single-node** option, idle
**autotermination**) in an isolated **Terraform workspace per use-case name**, so
`destroy` only removes that use case. Optionally deploys a use case's DAB bundle
and injects the cluster id.

## Use
```bash
cp .env.example .env        # DATABRICKS_HOST/TOKEN, CLOUD, MAX_WORKERS
make install                # databricks-sdk + python-dotenv  (also need: terraform, databricks CLI)

# point it at a use case's tfvars (which lives in that tool's repo)
lakebase plan    code_migration --vars /path/to/tool/deploy/code_migration.tfvars
lakebase deploy  code_migration --vars /path/to/tool/deploy/code_migration.tfvars --bundle /path/to/tool/deploy/bundle
lakebase destroy code_migration --vars /path/to/tool/deploy/code_migration.tfvars   # stops billing
lakebase list                # terraform workspaces (active use cases)
```
(`lakebase` = `python -m accelerator.cli`; also importable: `from accelerator import deploy, destroy, plan`.)

## Cost knobs (set in the tfvars the caller passes)
`use_spot` (spot workers, ~60–90% off; driver on-demand) · `single_node` (driver
only, cheapest) · `max_workers` (≤2) · `autotermination_minutes` · `node_type_id`
· `cloud` (aws/azure/gcp default node type). See `infra/terraform/usecases/example.tfvars`.

## Layout
```
accelerator/      cli.py (plan/deploy/destroy/list) · terraform.py · bundle.py · config.py
infra/terraform/  generic parametrized cluster + UC schema; usecases/example.tfvars
```

## Integrating a new use case
1. In your tool's repo, add a `*.tfvars` (copy `example.tfvars`) and, if you deploy
   assets, a DAB `bundle/`.
2. `lakebase deploy <name> --vars <your.tfvars> [--bundle <your/bundle>]`.
3. `lakebase destroy <name> --vars <your.tfvars>` when done.

No use case is hardcoded here — that's the point.
