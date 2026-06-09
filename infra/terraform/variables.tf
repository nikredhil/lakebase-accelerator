variable "databricks_host" {
  type        = string
  description = "Databricks workspace URL. Usually from DATABRICKS_HOST env var."
  default     = null
}

variable "databricks_token" {
  type        = string
  description = "Databricks PAT. Usually from DATABRICKS_TOKEN env var."
  sensitive   = true
  default     = null
}

variable "usecase" {
  type        = string
  description = "Use-case name. Drives resource naming so infra is use-case specific and independently destroyable."
  default     = "code_migration"

  validation {
    condition     = can(regex("^[a-z0-9_]+$", var.usecase))
    error_message = "usecase must be lowercase alphanumeric/underscore (used in resource names)."
  }
}

variable "cloud" {
  type        = string
  description = "Cloud the workspace runs on: aws | azure | gcp. Selects the default node type."
  default     = "aws"

  validation {
    condition     = contains(["aws", "azure", "gcp"], var.cloud)
    error_message = "cloud must be one of: aws, azure, gcp."
  }
}

variable "node_type_id" {
  type        = string
  description = "Override the worker/driver node type. Empty => per-cloud default from locals."
  default     = ""
}

variable "spark_version" {
  type        = string
  description = "Databricks Runtime version (LTS recommended)."
  default     = "15.4.x-scala2.12"
}

variable "min_workers" {
  type        = number
  description = "Autoscale floor."
  default     = 1
}

variable "max_workers" {
  type        = number
  description = "Autoscale ceiling. Manas constraint: 1-2 nodes max."
  default     = 2

  validation {
    condition     = var.max_workers >= 1 && var.max_workers <= 2
    error_message = "max_workers must be 1 or 2 (accelerator cost guardrail)."
  }
}

variable "autotermination_minutes" {
  type        = number
  description = "Idle minutes before the cluster auto-terminates (stops billing)."
  default     = 20
}
