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

# Job/all-purpose compute: 1 driver + autoscale 1..max_workers (<=2).
# autotermination + autoscale keep billing bounded; `terraform destroy` removes it.
resource "databricks_cluster" "this" {
  cluster_name            = "${local.prefix}-cluster"
  spark_version           = var.spark_version
  node_type_id            = local.node_type
  autotermination_minutes = var.autotermination_minutes

  autoscale {
    min_workers = var.min_workers
    max_workers = var.max_workers
  }

  spark_conf = {
    # Small-data friendly: keep the shuffle small so jobs don't over-partition.
    "spark.sql.shuffle.partitions" = "8"
  }

  custom_tags = local.tags
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
