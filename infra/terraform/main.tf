locals {
  # Per-cloud default node types (small / cheap — the accelerator runs small data).
  default_node_type = {
    aws   = "m5d.large"
    azure = "Standard_DS3_v2"
    gcp   = "n2-standard-4"
  }

  node_type = var.node_type_id != "" ? var.node_type_id : local.default_node_type[var.cloud]

  # Use-case-specific naming so each use case gets its own destroyable infra.
  prefix = "lakebase-${var.usecase}"

  tags = {
    project = "lakebase-accelerator"
    usecase = var.usecase
    managed = "terraform"
  }
}

# Smallest LTS runtime that matches the requested spark_version, resolved live.
data "databricks_spark_version" "lts" {
  long_term_support = true
  spark_version     = var.spark_version
}

data "databricks_current_user" "me" {}

# Job/all-purpose compute: 1 driver + autoscale 1..max_workers (<=2).
# autotermination + autoscale keep billing bounded; `terraform destroy` removes it.
resource "databricks_cluster" "this" {
  cluster_name            = "${local.prefix}-cluster"
  spark_version           = data.databricks_spark_version.lts.id
  node_type_id            = local.node_type
  autotermination_minutes = var.autotermination_minutes

  autoscale {
    min_workers = var.min_workers
    max_workers = var.max_workers
  }

  spark_conf = {
    # Single-node-friendly + small-data-friendly defaults.
    "spark.databricks.cluster.profile" = "singleNode"
    "spark.master"                     = "local[*, 4]"
  }

  custom_tags = local.tags
}

# A Unity Catalog schema scoped to the use case (assets land here; dropped on destroy).
resource "databricks_schema" "this" {
  catalog_name  = "main"
  name          = replace(local.prefix, "-", "_")
  comment       = "Use-case schema managed by the lakebase accelerator (${var.usecase})."
  force_destroy = true
}
