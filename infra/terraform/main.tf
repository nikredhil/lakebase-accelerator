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

# Current user — used to scope the single-user (UC-enabled) cluster for Databricks Connect.
data "databricks_current_user" "me" {}

# All-purpose compute: 1 driver + autoscale 1..max_workers (<=2). SINGLE_USER access
# mode makes it Unity-Catalog enabled and Databricks-Connect compatible.
# autotermination + autoscale keep billing bounded; `terraform destroy` removes it.
resource "databricks_cluster" "this" {
  cluster_name            = "${local.prefix}-cluster"
  spark_version           = var.spark_version
  node_type_id            = local.node_type
  autotermination_minutes = var.autotermination_minutes
  data_security_mode      = "SINGLE_USER"
  single_user_name        = data.databricks_current_user.me.user_name

  # Single-node = cheapest (driver only). Otherwise autoscale 1..max_workers (<=2).
  num_workers = var.single_node ? 0 : null
  dynamic "autoscale" {
    for_each = var.single_node ? [] : [1]
    content {
      min_workers = var.min_workers
      max_workers = var.max_workers
    }
  }

  spark_conf = merge(
    # Small-data friendly: keep the shuffle small so jobs don't over-partition.
    { "spark.sql.shuffle.partitions" = "8" },
    var.single_node ? {
      "spark.databricks.cluster.profile" = "singleNode"
      "spark.master"                     = "local[*]"
    } : {}
  )

  # Spot/preemptible workers for low cost; driver stays on-demand for stability.
  dynamic "azure_attributes" {
    for_each = var.cloud == "azure" && var.use_spot ? [1] : []
    content {
      availability       = "SPOT_WITH_FALLBACK_AZURE"
      first_on_demand    = 1
      spot_bid_max_price = -1 # -1 = up to the on-demand price (take the spot discount)
    }
  }
  dynamic "aws_attributes" {
    for_each = var.cloud == "aws" && var.use_spot ? [1] : []
    content {
      availability           = "SPOT_WITH_FALLBACK"
      first_on_demand        = 1
      spot_bid_price_percent = 100
    }
  }
  dynamic "gcp_attributes" {
    for_each = var.cloud == "gcp" && var.use_spot ? [1] : []
    content {
      availability = "PREEMPTIBLE_WITH_FALLBACK_GCP"
    }
  }

  custom_tags = merge(local.tags, var.single_node ? { ResourceClass = "SingleNode" } : {})
}

# Optional Unity Catalog schema for the use case's assets. Off by default because
# it assumes a "main" catalog with create rights; enable once UC is confirmed.
resource "databricks_schema" "this" {
  count         = var.create_schema ? 1 : 0
  catalog_name  = var.catalog_name
  name          = replace(local.prefix, "-", "_")
  comment       = "Use-case schema managed by the lakebase accelerator (${var.usecase})."
  force_destroy = true
}
