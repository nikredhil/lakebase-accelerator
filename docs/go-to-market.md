# Lakebase Accelerator — Go-To-Market & Use-Case Catalog

## Positioning
The Lakebase Accelerator turns **Lakebase (Databricks managed Postgres)** into a one-command,
cost-guarded **operational/serving layer co-located with the lakehouse**. One command spins
up a governed Postgres instance with a ready schema; one tears it down to stop billing.

**The four superpowers we sell on** (none of which a standalone Postgres has together):
1. **Zero-ETL to/from Delta** — operational data is co-located with the lakehouse; no pipelines to move it for analytics, eval, or training.
2. **Copy-on-write branching** — clone a database state in seconds for A/B, regression, what-if, or PII-safe dev copies.
3. **Scale-to-zero** — near-zero idle cost; consumption grows with real usage.
4. **Unity Catalog governance + pgvector** — one governed home for structured *and* unstructured/vector data.

## Ideal customer & buyers
- **Head of AI/ML Platform, VP Engineering** — agents, RAG, feature serving.
- **Data application teams** — operational apps and internal tools that need a real OLTP DB without leaving Databricks.
- **Platform/governance owners** — want one governed store instead of a sprawl of Redis + RDS + vector DB + sync jobs.

---

## Use-case catalog

### Flagship (packaged in this repo)
**1. Stateful Agent Backbone — agent memory + governed eval loop.**
Governed Postgres for short- + long-term agent memory, every interaction zero-ETL-synced to
Delta for eval/fine-tuning, branch-per-experiment memory sandboxes.
→ Full write-up: [`usecases/stateful-agent-backbone/README.md`](../usecases/stateful-agent-backbone/README.md) · schema: `migrations/agent/001_agent.sql` · buyer: Head of AI/ML Platform · effort: ~3–5 eng-weeks.

### Roadmap (proposed next adds — same caliber, not yet packaged)
**2. RAG / Knowledge Serving (governed vector layer).**
pgvector serving co-located with the source documents in the lakehouse; embeddings generated
via Model Serving, governed by UC, branch the index to experiment. The existing `docs` schema
module is the foundation. *Differentiation vs a standalone vector DB:* governed, co-located
with source-of-truth, and branchable. Buyer: AI engineering. Effort: ~3–4 eng-weeks.

**3. Online Feature & Inference Store.**
Low-latency feature serving from Lakebase, synced from Delta feature tables — closes the
train/serve skew gap with no separate online store + sync infra. Buyer: ML platform.
Effort: ~3–4 eng-weeks.

**4. Operational Apps on the Lakehouse.**
Power Databricks Apps / internal tools / customer dashboards directly off governed Postgres
reverse-synced from Delta — no bolt-on RDS. **Reference app already built:** the *MineLab
Supply Chain Digital Twin* (`digital-twin-poc-app/`) demonstrates the front-end + serving
pattern. Buyer: data app teams. Effort: ~2–4 eng-weeks.

**5. Eval & Experimentation Sandboxes (branch-per-experiment).**
Generalizes the flagship's branching: instant copy-on-write branches for A/B, regression,
what-if, and PII-safe prod-like dev copies. *Differentiation:* branching is unique to
Lakebase. Buyer: any team needing safe prod-like data. Effort: ~2 eng-weeks.

**6. Governed Decision / Audit Store.**
Append-only operational record of decisions, approvals, and overrides ("capture-at-decision"
institutional knowledge), with point-in-time branches for investigations and compliance.
Pairs with the dark-data direction. Buyer: ops/compliance. Effort: ~2–3 eng-weeks.

---

## Differentiation (generalized)
- **vs DIY** (Redis + Postgres + vector + pipelines): fragmented, ungoverned, and you ETL just to measure or analyze. The accelerator is one governed store, zero-ETL, branchable.
- **vs standalone Neon / RDS**: not co-located with lakehouse data; you still build pipelines to analyze/train. No data branching for sandboxes.
- **vs notebook-only prototypes**: no governance, no reproducibility, no cost guardrails or teardown.

## Packaging & pricing model
- **Effort to package a use case:** ~2–5 eng-weeks each (assembly of existing pieces + a schema module + demo notebook + optional Apps UI).
- **Run economics:** near-zero idle (scale-to-zero), grows with QPS/sessions/users — consumption story that ramps with adoption.
- **Cost guardrails (built in):** capacity capped at CU_2, stoppable instances, idle autotermination on any compute, mandatory cost-attribution tags.

## Reference assets in this repo
- **Control plane:** CLI (`accelerator/`), notebook (`notebooks/lakebase_control_panel.py`), and a Databricks Apps UI (`app/`) to deploy/stop/destroy instances.
- **Design spec:** `docs/design-spec.md` (minimal-input provisioning, generic schemas, unstructured/vector).
- **Schema modules:** `migrations/` (`meta`, `core`, `app`, `docs`, `agent`).
- **Architecture diagram:** `docs/architecture.mmd`.
- **Reference app:** `digital-twin-poc-app/` (MineLab twin — Operational App on the Lakehouse).

---

## Accelerator submission readiness
Checklist for submitting to the Databricks solution-accelerator review (status as of this repo):

| Item | Status | Notes |
|---|---|---|
| Clear value prop + buyer per use case | ✅ | This doc + flagship write-up |
| One-command deploy / teardown | ✅ | `lakebase deploy` / `destroy`; App UI |
| Reproducible schema | ✅ | Idempotent `migrations/` modules |
| Cost guardrails | ✅ | ≤ CU_2, scale-to-zero, autotermination, tags |
| Security & governance | ✅ (design) | SP-scoped calls, short-lived creds, UC + RLS in design spec |
| Demo / POC script | ✅ | Per-use-case demo (flagship has a 5-min flow) |
| Reference app | ✅ | MineLab twin |
| **Demo notebook (end-to-end)** | ⛏️ gap | Add a runnable `notebooks/` walkthrough per flagship (provision → seed → branch → eval-on-Delta) |
| **Migrator implementation** | ⛏️ gap | `migrations/` SQL exists; the applier (`accelerator/migrate.py`) is design-spec, not yet built |
| **Tests for new module** | ⛏️ gap | Add migration + smoke tests for `agent` module |
| **LICENSE + CONTRIBUTING** | ⛏️ check | Confirm present/standard before submission |

The two load-bearing gaps to close before review: a runnable end-to-end **demo notebook** for
the flagship, and the **migrator** that applies the modules (design-spec §8.2 / R2).
