# Demo Recording Script — "Manuka TwinOS: A Digital Retail & CPG Twin on Databricks Lakebase"

**Target runtime:** ~6–7 minutes
**Goal:** Show a working accelerator that (1) deploys a governed **Lakebase** backbone in one
click, and (2) runs **Manuka TwinOS** — a living retail & CPG digital twin — off it. Position
TwinOS as a *decision surface*, not another dashboard, and Lakebase as the unlock.

**Three messages the viewer must walk away with:**
1. Retail's problem isn't data, it's **coordination** — TwinOS turns siloed, lagging snapshots
   into one **live operational truth** and closes the gap between **signal and action**.
2. TwinOS is a **decision surface** — detect risk earlier, find root cause, and **test actions
   before they execute** (Lakebase branching), not just visualize the past.
3. **Lakebase is the unlock** — one governed backbone for the app, analytics, and AI agents
   (Lakebase + Unity Catalog + Lakehouse), deployed in one click. No stitched-together stack.

**The Lakebase value props to land (map each to something on screen):**
- **Transactional backbone for real-time apps + AI agents** → TwinOS reads/writes live state off Lakebase.
- **One foundation, not three** → no separate OLTP DB + analytics stack + AI app layer.
- **Sub-10ms reads, no ETL / auto-sync to Delta via Unity Catalog** → operational state *is* lakehouse-native.
- **Instant zero-copy branching** → simulate lead times, supplier reliability, replenishment, or promos off production.
- **State-store / checkpointer for AI agents** → the Genie-style copilot's memory lives in Lakebase.
- **Scale-to-zero, autoscaling** → pay only for the spiky, real-time workload.

**Production note — read before recording:** the live app is now branded **Manuka TwinOS**
(deployed and ACTIVE), so titles, sidebar, and copilot greeting already match this VO. The one
remaining gap is the underlying demo **data**, which is still supply-chain themed (suppliers,
detectors, rare-earth) rather than true retail/CPG (stores, SKUs, promotions). Until that data
is re-skinned, keep the camera on the brand-agnostic sections (Command Center, Network,
Scenarios, Copilot) and avoid lingering on SKU-level detail. On-screen cues below are written
brand-agnostic.

**Before you hit record — have these open in two tabs:**
- Tab A: **Lakebase Accelerator** app (Deploy + Cost center)
- Tab B: **Manuka TwinOS** dashboard (start on the Command Center)
- Optional: the Databricks **Database Instances** page, to show the instance appear.

---

## ACT 0 · Cold open — the coordination problem  (0:00 – 0:35)

> **[ON SCREEN]** TwinOS Command Center, dimmed behind the title.

**VO:**
"Retail and CPG leaders don't have a data problem. They have a **coordination problem**.
Inventory lives in one system, supplier updates in another, promotions in a third — and the
business is forced to decide from **lagging snapshots** instead of live operational truth.

And retail performance is won or lost in the gap between **signal and action**. A delayed
shipment, an underperforming promo, a regional stock imbalance — it erodes margin long before
it ever shows up in a report. — This is **Manuka TwinOS**: a living digital twin of the retail
network that closes that gap. And it's built on **Databricks Lakebase**."

---

## ACT 1 · The unlock — deploy the Lakebase backbone in one click  (0:35 – 2:35)

> **[ON SCREEN]** Tab A. Land on the **Deploy** tab. Header reads
> *"Lakebase Accelerator — Lakebase control plane: one click up, one click down."*

**VO:**
"A twin like this needs something most digital twins don't have: a **transactional backbone**
built for real-time apps and AI agents. Traditionally you'd stitch three things together — an
operational OLTP database, a separate analytics stack, and an AI app layer — with pipelines in
between. — TwinOS doesn't. It runs on **Lakebase**: Databricks' fully managed, serverless
Postgres, governed by **Unity Catalog**, sitting right next to the Lakehouse. One foundation,
not three. And the only hard part — standing it up — is now one click."

> **[ON SCREEN]** Hover the **capacity** selector (`CU_1` / `CU_2`); point at tags.

**VO:**
"Everything here is governed by default — tagged, cost-attributable, capacity-capped — and you
can stop compute any time: the data stays, the bill stops."

> **[ON SCREEN]** Enter a use-case name (e.g. `retail-twin`), keep `CU_1`, **click Deploy**.
> Show the instance appear (`STARTING`); optionally flip to the Database Instances page.

**VO:**
"One click. Behind the scenes it provisions a Lakebase Postgres instance as a service
principal, tags it, applies the schema. No tickets, no Terraform. In seconds we have a live,
governed endpoint — the operational backbone TwinOS runs on."

> **[ON SCREEN]** Switch to the **Cost center** tab. Show **Agent / App / Lakebase** buckets.

**VO:**
"And because finance always asks — here's the cost center, spend attributed per use case. This
is where serverless pays off: Lakebase **autoscales and scales to zero** when the twin is idle,
so for spiky, real-time retail workloads you pay only for what you consume. One-click backbone
*and* the governance story, in one place."

---

## BRIDGE · Connect the two  (2:35 – 2:55)

> **[ON SCREEN]** Briefly show the deployed instance endpoint, then cut to **Tab B**, TwinOS
> loading.

**VO:**
"So that's the backbone — deployed and governed. Now let's see what runs on it. **TwinOS is
reading live from the Lakebase instance we just stood up.** The dashboard needs fast
**operational** reads — OLTP — while the forecasting and risk models need **analytical**
horsepower — OLAP. One Lakebase store serves the live reads at single-digit milliseconds *and*
stays auto-synced to Delta for the analytics. **No ETL between them.** Let's walk the floor."

---

## ACT 2 · What TwinOS is — and what makes it different  (2:55 – 6:00)

> **[ON SCREEN]** **Command Center.** Let the hero row land: risk gauge, margin impact,
> on-time / on-shelf, then the KPI strip.

**VO:**
"TwinOS mirrors the moving parts of a modern retail and CPG network — **stores, fulfillment
nodes, suppliers, SKUs, promotions, inventory positions, orders, and demand signals** — as one
living model. — Top line: the three numbers an operator actually cares about — network risk,
margin at risk over 90 days, and on-shelf availability. Underneath, the leading indicators.
This is a **system of understanding**, not a rear-view dashboard — it's telling you you're
exposed *right now*."

> **[ON SCREEN]** Click the **critical event banner** → open the **Network** view. Pan the
> map; let the **event feed** scroll.

**VO:**
"Here's the live picture — a fulfillment disruption, a supplier slipping, a demand spike — fused
continuously against *your* network. Operational truth, not last week's extract."

> **[ON SCREEN]** Open **Root Cause & Scenarios.** Show the attribution, then run a **scenario**.

**VO:**
"And this is what makes it a **decision surface** instead of a visibility layer. First, **root
cause** — TwinOS attributes the exposure across **demand, supply, logistics, and commercial
actions** in one view: a few drivers explain most of the risk. — Then the part a normal database
can't do: **test the action before you execute it.** 'What if this supplier's lead time slips
two weeks?' To answer it safely, TwinOS **branches its own state** — Lakebase makes a
**zero-copy clone in seconds** — and simulates against the branch. Production never flinches.
You get a **P50 and a P90, in dollars**, with zero risk to what's running."

> **[ON SCREEN]** (Optional) gesture to multiple scenario options / a comparison.

**VO:**
"Change replenishment logic, supplier reliability, a promotional plan — simulate any of it in
an **isolated environment**, then push only the winner to production. That's branching for
retail decisions."

> **[ON SCREEN]** Open **Next-Best Actions.** Let the ranked plays show value vs cost.

**VO:**
"And it closes the loop from insight to **action** — a ranked playbook, each play with an
expected value, a cost, and a confidence. Roughly eleven million dollars protected for under a
million in cost. The business case, on one screen."

> **[ON SCREEN]** Open the **Copilot (Genie-style)**. Type a question; show metrics, sources,
> the SQL it ran.

**VO:**
"And for everyone who doesn't live in dashboards — a **conversational** way in. Ask in plain
language; it answers with the metrics, the sources, the query it ran, and walks you from root
cause to an approved plan. — Under the hood, Lakebase is the agent's **state-store** — its
checkpointer. The copilot pulls **short-term state** from Lakebase at millisecond latency and
reaches into the **lakehouse for the history**. One governed store for memory and action — and
every turn is logged back, ready for evaluation."

---

## ACT 3 · The bigger idea + close  (6:00 – 6:50)

> **[ON SCREEN]** Quick cut Tab A (instance / cost center) ↔ Tab B (Command Center). End on
> TwinOS.

**VO:**
"The teams closest to revenue all read from the same twin — **supply chain** catches
disruptions earlier, **merchandising** tests promotions against live conditions, **commercial**
ties execution risk to margin, and **data and AI teams** get one governed architecture for
apps, analytics, and agents.

The next generation of retail won't be static dashboards or isolated copilots. It'll be
**living operational models** that understand the network, reason over current conditions, and
help the business act faster. — That's **Manuka TwinOS**: a Databricks-native decision OS for
retail and CPG — and the backbone that makes it possible is **Lakebase**, deployed in one
click. Thanks for watching."

---

## Recording cheat-sheet

**Keep saying (the three messages):** *coordination problem, not a data problem* · *decision
surface, test before you execute* · *Lakebase is the unlock — one governed backbone.*

**Say "Lakebase" deliberately** at: the deploy click, the bridge, and the close. Minimum 3x.
**Say "TwinOS"** at the cold open, Act 2 open, and the close.

**Lakebase value props → where each lands (hit at least 4 of 6):**
| Prop | Say it at |
| --- | --- |
| Transactional backbone for real-time apps + agents | Act 1 deploy |
| One foundation, not three (no stitched stack) | Act 1 deploy · Close |
| Sub-10ms reads + no ETL (auto-sync to Delta via UC) | Bridge |
| Instant zero-copy branching → simulate before executing | Act 2 Scenarios (your strongest moment) |
| State-store / checkpointer for the copilot | Act 2 Copilot |
| Autoscaling / scale-to-zero | Act 1 Cost center |

**Value-by-team (Act 3 callout — name at least three):**
Supply chain · Merchandising · Commercial · Data & AI teams.

**Business-value anchors to hit out loud:** risk score → margin/revenue **at risk in $** →
**P50/P90** scenario number → **net EV** of the action plan ($11M protected / <$1M cost).

**Do:** move with intent, pause on the big numbers, let one chart fully render before talking.
**Don't:** read every KPI label, narrate every click, or dwell on UI chrome.
**If a number on screen differs from the VO**, trust the screen and say what's there.

**Optional 30-sec cut:** ACT 1 deploy click → BRIDGE → ACT 2 branching scenario + Next-Best
Actions → ACT 3 "decision OS for retail & CPG" close.
