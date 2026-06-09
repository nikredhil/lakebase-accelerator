# Lowest-cost cluster profile for the code_migration use case.
# Apply with: terraform apply -var-file=usecases/code_migration_lowcost.tfvars
#   (or point the accelerator at this file for a cheap, single-node run).
#
# One driver-only node (no workers), small VM, fast idle shutdown. Handles the
# small data sample fine; for real scale switch to code_migration.tfvars (1-2
# spot workers).

usecase                 = "code_migration"
cloud                   = "azure"
spark_version           = "15.4.x-scala2.12"
single_node             = true # driver-only: cheapest possible
use_spot                = true # (no effect with 0 workers, kept for clarity)
autotermination_minutes = 10   # shut down quickly when idle -> stop billing
