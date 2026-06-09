# Example use-case tfvars. A consuming tool keeps its own copy and passes it:
#   lakebase deploy <name> --vars /path/to/your.tfvars
# The accelerator also injects -var=usecase=<name> from the CLI.
cloud                   = "azure"
spark_version           = "15.4.x-scala2.12"
min_workers             = 1
max_workers             = 2     # 1-2 nodes
use_spot                = true  # spot/preemptible workers (driver on-demand)
single_node             = false # true = cheapest single driver-only node
autotermination_minutes = 15
