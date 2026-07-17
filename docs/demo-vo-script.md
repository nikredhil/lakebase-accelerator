# Manuka TwinOS — Demo VO (4-minute cut)

**Runtime:** ~3:50–4:00 at demo pace (~500 spoken words + action pauses).
Read straight through. **[ 🎬 ACTION ]** = what to do on screen. Bold = emphasis.

---

[ 🎬 Direct to camera. TwinOS Command Center dimmed behind you. ]

Retail and CPG leaders don't have a data problem — they have a **coordination problem**. Inventory in one system, suppliers in another, promotions in a third — so the business decides from lagging snapshots, not live operational truth. Retail is won or lost in the gap between **signal and action**: a delayed shipment or a weak promo erodes margin long before it shows up in a report. This is **Manuka TwinOS** — a living digital twin of the retail network that closes that gap, built entirely on **Databricks Lakebase**.

[ 🎬 Tab A. Deploy tab. Hover the capacity selector. ]

A twin like this needs a transactional backbone built for real-time apps and AI agents. Traditionally that's three stitched-together systems — an OLTP database, an analytics stack, and an AI layer — held together with pipelines. TwinOS runs on **one**: Lakebase, Databricks' serverless Postgres, governed by Unity Catalog, right next to the Lakehouse.

[ 🎬 Enter "retail-twin". Click Deploy. Show STARTING. ]

And standing it up is **one click** — it provisions a governed Lakebase instance, tags it, and applies the schema. No tickets, no Terraform. In seconds we have the live endpoint TwinOS runs on, governed by default and capacity-capped. Stop compute anytime: the data stays, the bill stops.

[ 🎬 Cost Center tab. ]

Spend is attributed per use case — and Lakebase scales to zero when the twin is idle, so for spiky retail workloads you pay only for what you use.

[ 🎬 Cut to Tab B. TwinOS loading. ]

Now, what runs on it. TwinOS reads **live** from the Lakebase instance we just deployed. The dashboard needs fast operational reads — OLTP — while forecasting and risk need analytical horsepower — OLAP. One Lakebase store serves the live reads in milliseconds and stays auto-synced to Delta. No ETL between them.

[ 🎬 Command Center. Let the hero row land. ]

TwinOS mirrors a retail network — stores, suppliers, SKUs, promotions — as one living model. Top line: **network risk, margin at risk over ninety days, and on-shelf availability**. This is a system of understanding, not a rear-view dashboard — it's telling you you're exposed right now.

[ 🎬 Root Cause & Scenarios. Run a scenario. ]

And it's a **decision surface**. Root cause attributes the exposure across demand, supply, logistics, and commercial actions. Then the part a normal database can't do: **test the action before you run it**. "What if this supplier's lead time slips two weeks?" TwinOS branches its own state — Lakebase makes a zero-copy clone in seconds and simulates against the branch. Production never flinches. You get a P50 and a P90, in dollars, with zero risk.

[ 🎬 Next-Best Actions. ]

Then it closes the loop to action — a ranked playbook, each play with an expected value, a cost, and a confidence. **Eleven million dollars protected for under one million in cost**. The business case on one screen.

[ 🎬 Copilot. Ask a question. ]

And a conversational way in: ask in plain language, and it answers with the metrics, the sources, and the query it ran. Under the hood, Lakebase is the agent's **state-store** — short-term memory in milliseconds, history from the lakehouse, every turn logged for evaluation.

[ 🎬 Back to camera. End on TwinOS. ]

The teams closest to revenue all read from the same twin — supply chain, merchandising, commercial, and data and AI. The next generation of retail won't be static dashboards or isolated copilots; it'll be **living operational models** that help the business act faster. That's **Manuka TwinOS** — a decision OS for retail and CPG, built on **Lakebase**, deployed in one click.
