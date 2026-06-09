output "cluster_id" {
  value       = databricks_cluster.this.id
  description = "Cluster id to run the use-case job against."
}

output "cluster_name" {
  value = databricks_cluster.this.cluster_name
}

output "schema_full_name" {
  value       = var.create_schema ? "${databricks_schema.this[0].catalog_name}.${databricks_schema.this[0].name}" : ""
  description = "Unity Catalog schema for this use case's assets (empty when create_schema=false)."
}

output "node_type_id" {
  value = local.node_type
}
