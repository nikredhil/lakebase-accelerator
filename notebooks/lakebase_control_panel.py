# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # Lakebase Accelerator Control Panel
# MAGIC
# MAGIC Spin up or tear down use-case infrastructure with a few clicks.
# MAGIC
# MAGIC 1. Set the widgets at the top (action, use case name, cloud, etc.)
# MAGIC 2. **Run All** to execute
# MAGIC
# MAGIC Everything uses the Databricks SDK — no external tools needed.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup & Widgets

# COMMAND ----------

dbutils.widgets.dropdown("action", "list", ["deploy", "destroy", "status", "list"], "Action")
dbutils.widgets.text("usecase", "example", "Use Case Name")
dbutils.widgets.dropdown("cloud", "azure", ["aws", "azure", "gcp"], "Cloud")
dbutils.widgets.dropdown("single_node", "true", ["true", "false"], "Single Node (cheapest)")
dbutils.widgets.text("max_workers", "2", "Max Workers (1-2)")
dbutils.widgets.text("custom_tags", "", "Custom Tags (team=x,cost_center=y)")
dbutils.widgets.text("autotermination_minutes", "20", "Auto-terminate (minutes)")

action = dbutils.widgets.get("action")
usecase = dbutils.widgets.get("usecase")
cloud = dbutils.widgets.get("cloud")
single_node = dbutils.widgets.get("single_node").lower() == "true"
max_workers = int(dbutils.widgets.get("max_workers"))
custom_tags_raw = dbutils.widgets.get("custom_tags")
autotermination = int(dbutils.widgets.get("autotermination_minutes"))

print(f"Action: {action} | Use Case: {usecase} | Cloud: {cloud} | Single Node: {single_node}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cluster Configuration
# MAGIC Per-cloud defaults, spot settings, and cost guardrails — mirrors the CLI's `dab.py` logic.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.compute import (
    AzureAttributes, AzureAvailability,
    AwsAttributes, AwsAvailability,
    GcpAttributes, GcpAvailability,
    AutoScale,
)

w = WorkspaceClient()
current_user = w.current_user.me().user_name

# Per-cloud default node types (small, cost-tuned)
DEFAULT_NODE_TYPES = {"aws": "m5d.large", "azure": "Standard_DS3_v2", "gcp": "n2-standard-4"}
node_type = DEFAULT_NODE_TYPES.get(cloud, "m5d.large")

# Cost guardrail
assert max_workers <= 2, f"max_workers must be <= 2, got {max_workers}"

# Base tags
tags = {
    "project": "lakebase-accelerator",
    "usecase": usecase,
    "managed": "notebook",
}
if custom_tags_raw:
    for pair in custom_tags_raw.split(","):
        if "=" in pair:
            k, v = pair.strip().split("=", 1)
            tags[k.strip()] = v.strip()

# Spark conf
spark_conf = {"spark.sql.shuffle.partitions": "8"}
if single_node:
    spark_conf["spark.databricks.cluster.profile"] = "singleNode"
    spark_conf["spark.master"] = "local[*]"
    tags["ResourceClass"] = "SingleNode"

print(f"Node type: {node_type}")
print(f"Tags: {tags}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Active Lakebase Deployments
# MAGIC All clusters tagged with `project=lakebase-accelerator`.

# COMMAND ----------

import pandas as pd

all_clusters = list(w.clusters.list())
lakebase_clusters = []
for c in all_clusters:
    ct = c.custom_tags or {}
    if isinstance(ct, dict) and ct.get("project") == "lakebase-accelerator":
        lakebase_clusters.append({
            "name": c.cluster_name,
            "cluster_id": c.cluster_id,
            "state": c.state.value if c.state else "UNKNOWN",
            "usecase": ct.get("usecase", ""),
            "node_type": c.node_type_id,
            "auto_terminate_min": c.autotermination_minutes,
        })

if lakebase_clusters:
    display(pd.DataFrame(lakebase_clusters))
else:
    print("No lakebase-accelerator clusters found in this workspace.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Execute Action

# COMMAND ----------

if action == "list":
    if lakebase_clusters:
        print(f"Found {len(lakebase_clusters)} lakebase cluster(s). See table above.")
    else:
        print("No lakebase clusters found.")

# ─── STATUS ──────────────────────────────────────────────────────────
elif action == "status":
    matching = [c for c in lakebase_clusters if c["usecase"] == usecase]
    if matching:
        for c in matching:
            print(f"  Cluster:  {c['name']}")
            print(f"  ID:       {c['cluster_id']}")
            print(f"  State:    {c['state']}")
            print(f"  Node:     {c['node_type']}")
            print()
    else:
        print(f"No lakebase cluster found for use case '{usecase}'.")

# ─── DEPLOY ──────────────────────────────────────────────────────────
elif action == "deploy":
    # Check if cluster already exists for this use case
    existing = [c for c in lakebase_clusters if c["usecase"] == usecase]
    if existing:
        print(f"Cluster already exists for '{usecase}': {existing[0]['cluster_id']} ({existing[0]['state']})")
        print("Destroy it first if you want to redeploy.")
    else:
        print(f"Deploying use case: {usecase} ...")

        # Build create request
        create_kwargs = dict(
            cluster_name=f"lakebase-{usecase}-cluster",
            spark_version="15.4.x-scala2.12",
            node_type_id=node_type,
            autotermination_minutes=autotermination,
            data_security_mode="SINGLE_USER",
            single_user_name=current_user,
            spark_conf=spark_conf,
            custom_tags=tags,
        )

        if single_node:
            create_kwargs["num_workers"] = 0
        else:
            create_kwargs["autoscale"] = AutoScale(min_workers=1, max_workers=max_workers)

        # Cloud-specific spot attributes
        if cloud == "azure":
            create_kwargs["azure_attributes"] = AzureAttributes(
                availability=AzureAvailability.SPOT_WITH_FALLBACK_AZURE,
                first_on_demand=1,
                spot_bid_max_price=-1.0,
            )
        elif cloud == "aws":
            create_kwargs["aws_attributes"] = AwsAttributes(
                availability=AwsAvailability.SPOT_WITH_FALLBACK,
                first_on_demand=1,
                spot_bid_price_percent=100,
            )
        elif cloud == "gcp":
            create_kwargs["gcp_attributes"] = GcpAttributes(
                availability=GcpAvailability.PREEMPTIBLE_WITH_FALLBACK_GCP,
            )

        resp = w.clusters.create_and_wait(**create_kwargs)
        print(f"\nCluster created!")
        print(f"  Name:       {resp.cluster_name}")
        print(f"  Cluster ID: {resp.cluster_id}")
        print(f"  State:      {resp.state.value}")
        print(f"\nRe-run with action='list' to see the updated table.")
        print(f"Run action='destroy' with usecase='{usecase}' when done to stop billing.")

# ─── DESTROY ─────────────────────────────────────────────────────────
elif action == "destroy":
    matching = [c for c in lakebase_clusters if c["usecase"] == usecase]
    if matching:
        for c in matching:
            print(f"  Permanently deleting cluster {c['cluster_id']} ({c['name']}) ...")
            w.clusters.permanent_delete(cluster_id=c["cluster_id"])
            print(f"  Deleted. Billing stopped.")
        print(f"\nDone. Use case '{usecase}' torn down.")
    else:
        print(f"No lakebase cluster found for use case '{usecase}'. Nothing to destroy.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Quick Reference
# MAGIC
# MAGIC | Action | What it does |
# MAGIC |--------|-------------|
# MAGIC | **deploy** | Creates a cost-tuned cluster for the use case (spot workers, autoscale, auto-terminate) |
# MAGIC | **destroy** | Permanently deletes the cluster — **stops all billing** |
# MAGIC | **status** | Shows cluster state for the specified use case |
# MAGIC | **list** | Shows all active lakebase clusters in this workspace |
# MAGIC
# MAGIC ### Cost Knobs
# MAGIC | Setting | Effect |
# MAGIC |---------|--------|
# MAGIC | `single_node = true` | Cheapest — driver only, no workers |
# MAGIC | `max_workers = 1` | Small (1 driver + 1 worker) |
# MAGIC | `max_workers = 2` | Default (1 driver + up to 2 spot workers) |
# MAGIC | Spot workers | On by default (~60-90% cheaper, driver stays on-demand) |
# MAGIC | Auto-termination | Cluster stops after N idle minutes (default: 20) |
