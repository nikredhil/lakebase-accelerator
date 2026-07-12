# Product inventory (for demo scripting)

Positioning: the repo is the **Lakebase Accelerator** — a Databricks Asset Bundle
control plane that spins up isolated, cost-guarded Lakebase (managed Postgres)
infrastructure per use case with one command, and tears it down with one command.
The apps below either ARE the product (control plane + flagship use case) or are
industry showcase demos built on the platform.

| App | What it is | Stack / how to run locally | Demo highlights |
|---|---|---|---|
| `app/` | **The product**: control-plane web UI (Databricks App) | FastAPI + vanilla JS, `uvicorn main:app` :8000 (needs Databricks creds) | Deploy tab (deploy/start/stop/destroy Lakebase per use case, one-click blueprints), Cost center (DBU→$ attribution, DIY-vs-Lakebase savings) |
| `agent_app/` | **Flagship use case live**: Stateful Agent Backbone chat app | FastAPI + langgraph + psycopg, uvicorn :8000 (needs live Lakebase) | Chat with Postgres-backed memory: LangGraph checkpointer, pgvector long-term memory, governed eval log with per-turn cost, thread branching for A/B |
| `usecases/stateful-agent-backbone/` | Use-case manifest + GTM narrative (not an app) | — | Buyer/pain/value-prop, architecture story, vs DIY/Neon/RDS |
| `accelerator/` + `notebooks/` | The CLI engine + Databricks notebook control panel | `python -m accelerator.cli` (needs creds); notebook is workspace-only | deploy/destroy/status/list, cost knobs (spot, single-node, 2-CU cap) |
| `digital-twin-poc-app/` | "Manuka TwinOS" retail/CPG supply-chain digital twin | React 19 TanStack Start, `npm run dev` :8000, **runs fully on mock data** | 8-section dashboard: KPIs, risk heatmap, supplier network map, Monte-Carlo scenarios, Genie NL copilot; rare-earth crisis story ($9–16M at risk) |
| `energy-field-ops/` | UK utility field-workforce copilot | React 19 + Vite, `npm run dev`, **no backend needed** | Leaflet map of engineers/jobs, weather-impact forecast, gantt, scripted copilot; `?theme=british-gas` brand switch |
| `energy-sustainability-esg/` | ESG Reporting Factory | FastAPI + prebuilt SPA in `ui/dist`, uvicorn, `DEMO_MODE=true` | AI report generation, compliance validation, lineage |
| `fence-sitter-finder-app/` | "VaccineIQ" pharma HCP fence-sitter intelligence | FastAPI serving prerendered static bundle, **zero data deps** | Fence-sitter scoring, next-best actions, customer 360, patient activation |
| `manuka-ai-obs-commandcenter-app/` | AI Observability Command Center | React 19 + FastAPI (needs SQL Warehouse for live data) | 11 pages: tool inventory, token intelligence, FinOps chargeback, compliance, streaming Genie SQL assistant — richest demo |

Easiest to capture locally with no credentials: `digital-twin-poc-app`,
`energy-field-ops`, `fence-sitter-finder-app` (mock/static data).
The React apps are the most visually impressive footage.
