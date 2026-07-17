# Lakebase Accelerator — App Overview

A **Databricks App** that acts as a one-click **control plane for Lakebase** (Databricks
managed Postgres). From a small red-and-white web UI a user can **deploy, start, stop, and
destroy** Lakebase database instances per use case, deploy packaged **solution blueprints**
(flagship: the *Stateful Agent Backbone*), and see a live **cost center** that attributes
spend across three buckets — Agent, App, and Lakebase.

It is a **FastAPI** backend serving a static vanilla-JS frontend, deployed via a Databricks
Asset Bundle. It is designed to run with minimal privileges: it works off uptime × published
rates when it can't read `system.billing`, and degrades gracefully everywhere.

> Source of truth: pulled from
> `/Workspace/Users/manas.reddy@manuka-ai.com/.bundle/lakebase-accelerator/dev/files/app`.
> The workspace copy and this local copy (`app/`) are identical **except** the workspace
> bundle also contains **`agent.py`** (the in-app reference agent — see *Agent backbone*
> below), which is not present in this local folder.

---

## What it does (at a glance)

The UI (`static/index.html` + `app.js`) has two tabs:

| Tab | What it does |
| --- | --- |
| **Deploy** | List managed Lakebase instances and their state/capacity/endpoint; deploy a new instance for a named use case (capacity `CU_1`/`CU_2`, optional retention + tags); start/stop compute; destroy (purge). Also lists **blueprints** for one-click packaged deploys. |
| **Cost center** | DBU→$ attribution across **Agent / App / Lakebase** for a chosen window, plus a forward **estimate** calculator and a **DIY-vs-Lakebase savings** comparison. |

The header shows the workspace host and signed-in user; a link to a separate **Agent
Backbone** app appears if that app is deployed in the workspace.

---

## Tech stack

- **Backend:** Python, **FastAPI** + **uvicorn**, **databricks-sdk**. Optional **psycopg**
  (lazy-imported) for Postgres access, optional **langgraph** for checkpointer setup.
- **Frontend:** static `index.html` + ~515 lines of vanilla `app.js` + `style.css`
  (no build step). Databricks red (`#FF3621`) branding.
- **Runtime:** `app.yaml` → `uvicorn main:app --host 0.0.0.0 --port 8000` (Databricks Apps).
- **Auth:** all workspace calls run as the **app's service principal** (credentials injected
  by the Apps runtime); the forwarded user token only has read scopes and can't drive the
  database API.

---

## How it's structured

```
app/
├── app.yaml            # Apps run command (uvicorn on :8000)
├── requirements.txt    # fastapi, uvicorn, databricks-sdk, psycopg[binary]
├── main.py             # FastAPI app — all HTTP routes
├── service.py          # Lakebase provisioning (deploy/destroy/start/stop/list) via SDK Database API
├── blueprints.py       # packaged use cases (Stateful Agent Backbone) + SQL module loader
├── costs.py            # cost center: uptime×rate model + optional system.billing SQL
├── pricing.py          # SINGLE SOURCE OF TRUTH for all rates/assumptions (pure, no SDK)
├── db.py               # Lakebase Postgres connectivity + apply_schema (psycopg, lazy)
├── agent.py            # (workspace bundle only) in-app reference agent over the backbone
├── sql/                # vendored schema modules (00_prelude, 01_ledger, 02_core, 03_agent)
└── static/             # index.html, app.js, style.css  (the UI)
```

### HTTP API (`main.py`)

| Method & path | Purpose |
| --- | --- |
| `GET /api/config` | host, cloud, user, allowed capacities, agent-app URL |
| `GET /api/deployments` | list managed Lakebase instances (summaries) |
| `POST /api/deploy` | create an instance for a use case |
| `POST /api/destroy` | delete + purge an instance |
| `POST /api/instances/{name}/start` · `/stop` | toggle compute (data retained on stop) |
| `GET /api/blueprints` · `/{slug}/schema` · `POST /{slug}/deploy` | list/inspect/deploy blueprints |
| `GET /api/costs` | live cost center (Agent/App/Lakebase) |
| `GET /api/costs/estimate` | rate-based forward estimate |
| `GET /` + `/static` | serve the UI |

---

## Key behaviors & design choices

**Provisioning (`service.py`).** One Lakebase **database instance per use case** via the SDK
Database API. The **workspace is the source of truth**: managed instances are discovered by a
`lakebase_project = lakebase-accelerator` custom tag (with `x_`-prefixed and name-prefix
`lakebase-` fallbacks, because some workspaces silently rename colliding tag keys). Cost
guardrails are baked in: **capacity capped at `CU_2`** (no CU_4/CU_8), instances can be
**stopped** (compute billing stops, storage/data retained), and **destroy purges** storage so
billing fully stops.

**Blueprints (`blueprints.py`).** Packaged, one-click use cases. The single flagship —
**Stateful Agent Backbone** — provisions a `CU_1` instance (`lakebase-agent-backbone`) and
carries the marketing narrative (value props, differentiation vs DIY/Neon/RDS, next steps)
plus the **schema modules** to apply (`meta`, `core`, `agent`). SQL is loaded from the
vendored `app/sql/` dir, falling back to the canonical `/migrations` tree for local dev.

**Cost center (`costs.py` + `pricing.py`).** Three buckets — **Agent / App / Lakebase**. The
**primary live source needs no billing grants**: cost-to-date = published DBU $/hr × hours each
resource has been up. `system.billing.usage ⋈ list_prices` is queried *opportunistically* via
a SQL warehouse to enrich the granular breakdown, but is never required. The **Agent** bucket
is measured precisely per-turn from the co-located `agent.interactions` ledger inside the
backbone's Postgres. The module **never raises to the route** — it falls back to a pure
rate-based estimate with a "what to grant" note. `pricing.py` is the single source of truth
for every rate (Lakebase 0.213 DBU/CU-hr, Apps 0.5/1.0 DBU/hr, `$0.55`/DBU, per-model token
rates), overridden at runtime by the workspace's own list prices when available.

**Agent backbone (`agent.py` + `db.py`) — workspace bundle only.** A reference agent that
demonstrates what the backbone enables: it calls a Databricks **Foundation Model serving
endpoint** for chat (pay-per-token, scale-to-zero), uses **Lakebase for memory** — short-term
thread state in `agent.interactions` (+ LangGraph `checkpoint*` tables) and long-term
**semantic memory** in `agent.memories` (pgvector recall via `databricks-bge-large-en`) — and
writes **every turn with a computed `cost_usd`** so the cost center's Agent bucket is a
governed, co-located ledger. It can **branch** a thread's memory under a new label for A/B and
regression testing. `db.py` connects to the instance's Postgres as the SP using a short-lived
OAuth credential, applies the vendored schema, and exposes a thin query helper (psycopg
imported lazily so the app boots without it). *Note:* the deployed `main.py` does not import
`agent.py`; it's wired in via the separate Agent Backbone app / a future Agent tab.

---

## How it's deployed

This `app/` folder is the deployable unit of the **`lakebase-accelerator` Databricks Asset
Bundle** (repo root `databricks.yml`). The container ships only `./app`, which is why the
SQL migrations are **vendored** into `app/sql/` (kept in sync with `/migrations`).

```bash
databricks bundle validate -t dev
databricks bundle deploy   -t dev
databricks bundle run <app-resource>     # starts the Apps compute
```

For the **live cost center** to go beyond uptime estimates, grant the app's service principal
`SELECT` on `system.billing` and `CAN_USE` on a SQL warehouse (see
`scripts/grant_app_access.py`). For the **agent backbone** features, the app SP needs rights to
manage database instances and a deployed `lakebase-agent-backbone` instance.

---

## In one line

A minimal-privilege **Lakebase control plane**: deploy/stop/destroy managed Postgres per use
case, ship the Stateful Agent Backbone blueprint as a one-click deploy, and watch governed
Agent/App/Lakebase spend — all as a FastAPI Databricks App that degrades gracefully when
permissions or data are missing.
