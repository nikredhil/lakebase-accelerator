# Start With Lakebase: Building Manuka TwinOS, a Real-Time Retail & CPG Twin

If you're building anything **real-time and stateful** on Databricks — a digital twin, a simulation, an AI agent — start with **Lakebase**. It's Databricks' fully managed, serverless Postgres, and it collapses the one architectural seam that usually wrecks these systems: the wall between your **operational database** and your **lakehouse**. One store, millisecond reads, zero ETL.

To prove it, we built **Manuka TwinOS** — a living digital twin of a retail & CPG network — entirely on Lakebase. It scores network risk live, simulates disruptions, and recommends mitigations in dollars, and the whole backbone deploys in **one click**. This post is about the database first, and the twin as the receipt.

## What Lakebase Is

Lakebase is **Postgres** — the database you already know, with the drivers, SQL, and extensions you already use — but delivered as a **serverless, lakehouse-native** service. Three properties matter most:

- **Serverless & scale-to-zero.** Compute autoscales with load and idles to zero. You pay for the spikes a real-time workload actually produces, not for an instance sitting hot 24/7.
- **Sub-10ms reads, high concurrency.** It's built for continuous operational traffic — rapid state updates and point reads — not just analytical scans.
- **Zero-ETL sync to Delta via Unity Catalog.** The rows your app writes are automatically available as **governed Delta tables** for analytics and ML. Operational and analytical data are the *same data*, under one catalog.

That last point is the whole game. Your transactional store and your lakehouse stop being two systems you bridge — they become **one governed store**.

## Why It Changes the Architecture

Most stateful systems have a split personality. Half of the work is **OLTP**: read the current state, write an update, do it in milliseconds, do it constantly. The other half is **OLAP**: scan months of history, run a thousand simulations, train a model.

The classic answer is two databases joined by **ETL** — and that seam is where these systems go to die. Data is stale by the time it crosses, latency balloons, costs stack, and governance fragments across two platforms.

Here's the thing: the business doesn't experience that seam as "an ETL problem." It experiences it as a **coordination problem**. Inventory lives in one system, supplier updates in another, promotions in a third — and teams are forced to decide from **lagging snapshots instead of live operational truth**. **Lakebase removes the seam**, which is what makes a single source of operational truth possible in the first place.

## The Proof: Manuka TwinOS

**Manuka TwinOS** mirrors the moving parts of a modern retail & CPG ecosystem — **stores, fulfillment nodes, suppliers, SKUs, promotions, inventory positions, orders, and demand signals** — as one living model. The payoff is a **system of understanding, not a rear-view dashboard**: retail performance is won or lost in the gap between **signal and action**, and a delayed shipment or an underperforming promo erodes margin long before it shows up in reporting. TwinOS closes that gap.

Every piece of it runs on Lakebase:

- The dashboard reads **live network state** from Lakebase at single-digit-millisecond latency — the OLTP half.
- The forecasting and risk models run against the **same state, synced to Delta** with no pipeline — the OLAP half.
- The copilot's memory and interaction log live there too (more below).

And it's not just a visibility layer — it's a **decision surface**. On one Databricks-native architecture, TwinOS lets teams:

- **Detect stockout and fulfillment risk earlier** off a live operational twin.
- **Investigate root cause** across demand, supply, logistics, and commercial actions in one view.
- **Test actions before they execute** — simulate them safely (next section).
- **Ask in plain language** through a Genie-style copilot and AI agents.
- **Move from insight to action** without leaving the platform.

No seam, no ETL job, no second database. TwinOS is just an app on top of one Postgres endpoint.

## Step One: Deploy the Backbone in One Click

Before the twin runs, you need that Lakebase instance — provisioned, tagged, governed, cost-capped. That's the **Lakebase Accelerator**: a control plane that turns "file a ticket and write Terraform" into a button. Under the hood it's a thin call to the Databricks Database API, run as the app's service principal:

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import DatabaseInstance, CustomTag

w = WorkspaceClient()  # runs as the app's service principal — no PATs

# Provision the twin's operational backbone: serverless Postgres, governed by default.
w.database.create_database_instance(DatabaseInstance(
    name="manuka-twinos",
    capacity="CU_1",  # cost guardrail; autoscales and scales to zero when idle
    custom_tags=[CustomTag(key="lakebase_project", value="twinos")],  # cost-attributed
))
```

A few seconds later you have a live, governed Postgres endpoint with its spend already attributed in a cost center. **That endpoint is what TwinOS runs on.**

## The Trick: Branch Your State Like Code

This is the part a normal database can't do — and where Lakebase turns TwinOS from a dashboard into a decision surface.

When a planner asks *"what if our top supplier's lead time slips two weeks, right before the holiday promo?"*, you do **not** want to mutate production to find out. With Lakebase you don't: you **branch** the live instance — a **copy-on-write clone, ready in seconds, with no data physically copied** — simulate against the branch, and discard it.

> **Analogy:** it's `git branch` for your database. Cut a branch off `main`, experiment freely, and production never sees it. Merge nothing; just delete the branch when you're done.

```python
# 1. Branch the live twin — copy-on-write, seconds, zero data copied.
branch = w.database.create_database_instance(DatabaseInstance(
    name="twinos-whatif",
    parent_instance_ref=prod_ref,  # fork the production instance's state
    capacity="CU_1",
))

# 2. Run the scenario against the BRANCH, not prod.
result = run_scenario(branch.read_write_dns, lead_time_delta_days=14, event="holiday-promo")

# 3. Done — drop it. Production never flinched.
w.database.delete_database_instance(branch.name, purge=True)
```

That's how teams **test lead times, supplier reliability, replenishment logic, or promotional plans** in isolated environments and get a **P50 and a P90 in dollars** — with zero risk to the running system. Spin up ten branches in parallel to A/B different mitigations, or validate a new ML model against real state before it ever touches production.

## Where the AI Copilot Plugs In

TwinOS ships with a natural-language copilot, and Lakebase is its **state-store** — its checkpointer. Short-term conversation and twin state come from Postgres at millisecond latency; long-term history lives in the lakehouse. Even **semantic memory** is just Postgres, via `pgvector` — no separate vector database to run:

```sql
-- Long-term recall straight from Lakebase: nearest memories by cosine distance.
SELECT content
FROM   agent.memories
WHERE  scope_id = %s AND embedding IS NOT NULL
ORDER  BY embedding <=> %s::vector   -- pgvector similarity, in the same DB
LIMIT  5;
```

Every turn — with its token cost — is written back to the same store, so the **interaction log doubles as a governed, zero-ETL evaluation dataset**. The thing serving the agent's memory is the same thing you train and measure on. That's the **transactional backbone for real-time apps and AI agents** most digital twins lack: instead of stitching together a separate OLTP database, an analytics stack, and an AI app layer, you get one governed foundation — Lakebase + Unity Catalog + the Lakehouse.

## Where It Creates Value

TwinOS is built for the teams that sit closest to revenue, margin, and service outcomes — and they all read from the same live twin:

| Team | How TwinOS helps |
| --- | --- |
| **Supply chain** | Detects disruptions earlier, quantifies downstream risk, and prioritizes corrective actions. |
| **Merchandising** | Evaluates promotion and assortment impact against live operational conditions. |
| **Commercial** | Connects execution risk to sales and margin outcomes in a business-friendly interface. |
| **Data & AI teams** | Delivers one governed architecture for apps, analytics, and agent workflows. |

One twin, one governed store — four very different jobs to be done.

## The Bigger Idea

The next generation of retail systems won't be defined by static dashboards or isolated AI copilots. They'll be defined by **living operational models** that understand the network, reason over current conditions, and help the business act faster. Manuka TwinOS is that model — a Databricks-native **decision OS for retail and CPG** — and the reason it can exist at all is the transactional backbone underneath it.

## Gotchas & Next Steps

A few things to keep in mind before you build on this:

- **Branches aren't free — clean them up.** A zero-copy branch still bills for the compute it runs. Treat them like feature branches: ephemeral, and `purge=True` when done.
- **It's Postgres, not a cache.** Sub-10ms reads, yes — but it's a database with connection limits and short-lived OAuth credentials (refresh before the ~1h TTL). Pool your connections.
- **Govern with tags from day one.** Cost attribution and discovery hang off custom tags. Some workspaces rename colliding keys to `x_<key>` — plan for it.
- **Know your source of truth.** The zero-ETL bridge to Delta is the magic; be clear which tables are operational-source-of-truth vs. analytics-synced so you don't double-write.

**Start here:** deploy a `CU_1` Lakebase instance with the accelerator, point a read at it, and watch it appear as a Delta table with no pipeline. Then branch it and run a what-if. Once you've felt *operational and analytical, one store, no seam*, you won't wire ETL between two databases again.

*Start with Lakebase. Manuka TwinOS is just what it looks like when you do.*
