# Stateful Agent Backbone — agent memory + governed eval loop

**Flagship use case for the Lakebase Accelerator.** Not "agent memory 101" — the
differentiator is **closing the loop**: every agent interaction lands in governed Postgres
**co-located with the lakehouse**, so eval, fine-tuning, and analytics happen with **zero
ETL**, and copy-on-write **branching** gives you isolated memory sandboxes for regression
testing.

## Buyer & pain
- **Buyer:** Head of AI/ML Platform, VP Engineering.
- **Pain:** Agents going to prod are stateless. Teams bolt on Redis + a separate Postgres +
  a vector DB + brittle pipelines just to get traces out for eval. No governance, no
  reproducibility, no clean path from "it works in a notebook" to "it's in prod and we can
  measure it."

## Value prop
- **One governed store** for short- and long-term memory — LangGraph
  `langgraph-checkpoint-postgres` checkpointer (short-term thread state) + Lakebase
  (long-term semantic memory, the `agent` schema module).
- **Zero-ETL eval/fine-tuning** — every interaction is written to `agent.interactions` and
  synced to Delta, so quality measurement and training data prep need no pipelines.
- **Branch a memory state in seconds** to A/B agent versions or run regression suites on an
  isolated copy. Consumption scales with every user session.

## How it works on Lakebase
```
  Agent (Mosaic AI Agent Framework / serving endpoint)
     │  LangGraph checkpointer            │  app writes
     ▼  (short-term thread state)         ▼  (long-term memory + every turn)
  ┌─────────────── Lakebase (governed Postgres, scale-to-zero) ───────────────┐
  │  checkpoints* (LangGraph-managed)   agent.threads      agent.memories (pgvector) │
  │                                     agent.interactions  agent.feedback / eval_runs │
  └───────────────┬──────────────────────────────────────────────────────────┘
                  │  zero-ETL sync (UC-governed)        ⎇ copy-on-write branch
                  ▼                                     ▼
        Delta (eval / fine-tuning / BI)        isolated memory sandbox (A/B, regression)
```
\* LangGraph creates `checkpoints*` tables via `checkpointer.setup()`; this module owns the
`agent.*` application + eval layer (see `migrations/agent/001_agent.sql`).

## What the accelerator provisions
- A cost-guarded Lakebase instance (scale-to-zero; `standard` profile = CU_1).
- The **`agent` schema module** — `threads`, `interactions` (append-only eval log),
  `memories` (pgvector long-term recall), `feedback`, `eval_runs`.
- Manifest: [`lakebase.yaml`](./lakebase.yaml) — `schema.modules: [core, agent]`, vectors on,
  multi-tenant on.

## Differentiation
| vs | Why Lakebase wins |
|---|---|
| **DIY** (Redis + Postgres + vector + eval pipeline) | Fragmented and ungoverned; you ETL just to *measure* quality. One store here, governed, zero-ETL. |
| **Standalone Neon / RDS** | Memory isn't co-located with training data — you still pipe traces to the lakehouse. Lakebase is co-located by design. |
| **Any other managed Postgres** | Lakebase is the only one with **copy-on-write data branching** for instant eval/memory sandboxes. |

## Pricing & effort
- **~3–5 eng-weeks to package** — mostly assembly (reference agent on Mosaic AI Agent
  Framework + checkpointer + this memory schema + eval notebooks + sync-to-lakehouse + a
  Databricks Apps chat UI).
- **Run cost near-zero idle** (scale-to-zero), grows with QPS. Lands with teams already on
  Mosaic AI / Agent Bricks; expands as agent traffic ramps.

## Demo / POC (single workspace, ~5 min)
1. Agent on a serving endpoint → Lakebase stores thread state.
2. **Resume** a conversation mid-task (checkpointer rehydrates state).
3. **Branch** the memory DB, change the prompt/model, re-run the same threads side-by-side.
4. Flip to a **Delta dashboard** showing interactions auto-synced for eval.

## Provision
```bash
lakebase up agent-backbone --manifest usecases/stateful-agent-backbone/lakebase.yaml
# ... build agents against the endpoint; lakebase destroy agent-backbone when done
```
