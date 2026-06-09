# Use-case-specific Terraform variables for `code_migration`.
# Applied via: terraform apply -var-file=usecases/code_migration.tfvars
# (the accelerator CLI wires this automatically and uses a per-usecase workspace).

usecase                 = "code_migration"
cloud                   = "azure"
spark_version           = "15.4.x-scala2.12"
min_workers             = 1
max_workers             = 2 # 1-2 nodes max
autotermination_minutes = 15 # idle shutdown -> stops billing sooner

# --- low-cost knobs ---
use_spot    = true  # spot/preemptible workers (~60-90% cheaper; driver stays on-demand)
single_node = false # set true for the cheapest run: 1 driver-only node, no workers
# node_type_id = "Standard_DS3_v2"  # uncomment to pin/override the (already small) default
