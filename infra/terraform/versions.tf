terraform {
  required_version = ">= 1.5.0"

  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.50"
    }
  }
}

# Auth resolves from DATABRICKS_HOST / DATABRICKS_TOKEN env vars (all clouds),
# or from a Databricks CLI profile. Kept cloud-agnostic on purpose.
provider "databricks" {
  host  = var.databricks_host
  token = var.databricks_token
}
