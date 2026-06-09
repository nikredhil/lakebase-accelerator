output "cluster_id" {
  value       = databricks_cluster.this.id
  description = "Cluster id to run the use-case job against."
}

output "cluster_name" {
  value = databricks_cluster.this.cluster_name
}

output "schema_full_name" {
  value       = "${databricks_schema.this.catalog_name}.${databricks_schema.this.name}"
  description = "Unity Catalog schema for this use case's assets."
}

output "node_type_id" {
  value = local.node_type
}
