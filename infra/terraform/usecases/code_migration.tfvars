# Use-case-specific Terraform variables for `code_migration`.
# Applied via: terraform apply -var-file=usecases/code_migration.tfvars
# (the accelerator CLI wires this automatically and uses a per-usecase workspace).

usecase                 = "code_migration"
cloud                   = "aws" # overridden by CLOUD env / accelerator at runtime
spark_version           = "15.4.x-scala2.12"
min_workers             = 1
max_workers             = 2 # 1-2 nodes max
autotermination_minutes = 20
