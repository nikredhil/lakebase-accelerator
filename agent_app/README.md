# Lakebase Agent Backbone app

The live **Stateful Agent Backbone** — a Databricks App (name
`lakebase-agent-backbone`) that chats against a Lakebase instance whose memory
is governed Postgres co-located with the lakehouse.

- Short-term thread state → LangGraph `langgraph-checkpoint-postgres` checkpointer.
- Long-term memory → `agent.memories` (pgvector recall via `databricks-bge-large-en`).
- Every turn → `agent.interactions` (append-only eval log, with per-turn `cost_usd`).
- **Branch** a thread to A/B agent versions / models on an isolated memory copy.

Deploy the backbone **instance** from the control-plane app
(`lakebase-accelerator` → Deploy → flagship blueprint), then point this app at it.

## Shared modules
`service.py`, `pricing.py`, `blueprints.py`, `db.py`, `agent.py`, and `sql/` are
**copies** of the control-plane app's modules (Databricks Apps deploy one source
tree per app). Keep them in sync via `make sync-agent-app`.
