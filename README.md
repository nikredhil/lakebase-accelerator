# Lakebase Accelerator

A **reusable, use-case-agnostic Databricks infra-as-code control plane** built on
Databricks Asset Bundles (DAB). One command spins up the infra behind a use case;
one tears it down to stop billing. Deploy multiple use cases simultaneously, each
with its own isolated resources and custom tags.

```
                ┌──────────── lakebase accelerator ──────────────┐
  your tool ──► │  lakebase deploy <name> [--var k=v] [--tags ..]│
  (or notebook) │     DAB (cluster, schema, assets)              │
                └────────────────────────────────────────────────┘
```

## What it provisions
A small, cost-tuned cluster (per-cloud default node type, autoscale **1-2 nodes**,
**spot/preemptible** workers with on-demand fallback, **single-node** option, idle
**autotermination**) in an isolated DAB deployment per use-case name. Optionally
creates a Unity Catalog schema. `destroy` only removes that use case.

## Quick start
```bash
cp .env.example .env        # DATABRICKS_HOST/TOKEN, CLOUD, etc.
make install                # databricks-sdk, pyyaml, python-dotenv (also need: databricks CLI)

lakebase deploy  code_migration                                     # deploy with env defaults
lakebase deploy  code_migration --vars-file usecases/example.json   # deploy with overrides
lakebase deploy  etl_pipeline --var cloud=aws --tags team=data      # second use case
lakebase status  code_migration                                     # check cluster state
lakebase list                                                       # all active deployments
lakebase destroy code_migration                                     # stops billing
```
(`lakebase` = `python -m accelerator.cli`; also importable: `from accelerator import deploy, destroy, plan, status`.)

## Notebook UI
Open `notebooks/lakebase_control_panel.py` in your Databricks workspace. It provides
widget-based controls to deploy, destroy, and monitor use cases without touching the CLI.

## Streamlit UI (local)
A colorful local control plane over the CLI: set cost knobs → Plan / Deploy / Status /
Destroy, plus a live cluster + warehouse panel with status badges.
```bash
make install-ui     # pip install -r app/requirements.txt
make ui             # streamlit run app/streamlit_app.py
```

## Cost knobs
`use_spot` (spot workers, ~60-90% off; driver on-demand) | `single_node` (driver
only, cheapest) | `max_workers` (<=2) | `autotermination_minutes` | `node_type_id`
| `cloud` (aws/azure/gcp default node type). Set via `--var`, `--vars-file`, or env vars.

## Custom tags
```bash
lakebase deploy myuc --tags team=data-eng,cost_center=1234
# or via env: LAKEBASE_CUSTOM_TAGS="team=data-eng,cost_center=1234"
# or in vars-file JSON: {"custom_tags": {"team": "data-eng"}}
```
Base tags (`project`, `usecase`, `managed`) are always applied.

## Layout
```
accelerator/        cli.py · dab.py · config.py
notebooks/          lakebase_control_panel.py (Databricks UI)
usecases/           example.json (variable override template)
databricks.yml      top-level DAB bundle (syncs code + notebook to workspace)
tests/              unit + e2e tests
```

## Integrating a new use case
1. `lakebase deploy <name>` — uses env defaults, or pass `--vars-file` / `--var` overrides.
2. `lakebase destroy <name>` when done — stops billing.
3. Multiple use cases can be deployed simultaneously.

## Testing
```bash
make test           # unit tests (no credentials needed)
make test-e2e       # full deploy/destroy lifecycle (needs DATABRICKS_HOST/TOKEN)
```
