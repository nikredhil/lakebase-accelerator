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

## Web UI (Databricks App)
A red/white control-plane UI lives in `app/` and deploys as a Databricks App.
It provisions **Lakebase (managed Postgres) database instances** — one isolated
instance per use case, capacity capped at 2 CU as a cost guardrail:
```bash
databricks bundle deploy -t dev             # creates the app resource
databricks bundle run lakebase_ui           # pushes source + starts the app
databricks apps stop lakebase-accelerator   # stop app compute when not in use
```
Instances are discovered via their `lakebase_project` custom tag (plus a
`lakebase-` name-prefix fallback) — no local state. From the browser you can
deploy, stop/start (pauses compute billing, keeps data), destroy (deletes data),
and copy each database's Postgres endpoint. All workspace calls run as the
app's service principal.

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
app/                Databricks Apps control-plane UI (deploy/stop/destroy instances)
notebooks/          lakebase_control_panel.py (Databricks UI)
migrations/         schema modules: meta · core · app · docs · agent
usecases/           per-use-case manifests (e.g. stateful-agent-backbone/) + example.json
docs/               design-spec.md · go-to-market.md · architecture.mmd
databricks.yml      top-level DAB bundle (syncs code + notebook to workspace)
tests/              unit + e2e tests
```

## Use cases
Packaged, reviewable solutions on top of the control plane. Full catalog, differentiation,
pricing/effort and the accelerator-submission checklist live in
[`docs/go-to-market.md`](docs/go-to-market.md).

- **Stateful Agent Backbone** (flagship) — agent memory + governed eval loop:
  [`usecases/stateful-agent-backbone/`](usecases/stateful-agent-backbone/README.md)
  (schema module `migrations/agent/001_agent.sql`).
- Roadmap: RAG / knowledge serving · online feature store · operational apps on the lakehouse
  (reference app: `digital-twin-poc-app/`) · branch-per-experiment eval sandboxes · governed
  decision/audit store.

### Integrating a new use case
1. `lakebase deploy <name>` — uses env defaults, or pass `--vars-file` / `--var` overrides.
2. `lakebase destroy <name>` when done — stops billing.
3. Multiple use cases can be deployed simultaneously.

## Testing
```bash
make test           # unit tests (no credentials needed)
make test-e2e       # full deploy/destroy lifecycle (needs DATABRICKS_HOST/TOKEN)
```
