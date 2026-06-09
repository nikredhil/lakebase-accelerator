.PHONY: install install-spark data test run plan deploy destroy dryrun clean

PY ?= python3

install:                 ## install core deps (no spark)
	$(PY) -m pip install -r requirements.txt

install-spark:           ## local dry-run extras (NOT alongside databricks-connect)
	$(PY) -m pip install pyspark

data:                    ## generate the small mock data sample
	$(PY) -m usecases.code_migration.data.generate_mock_data

test:                    ## run local tests (no workspace / no API key needed)
	$(PY) -m pytest tests -q

run:                     ## run the use-case pipeline locally (dry-run PR)
	$(PY) -m usecases.code_migration.run --example all --backend local

plan:                    ## terraform validate + plan + bundle validate (no infra change)
	$(PY) -m accelerator.cli plan code_migration

deploy:                  ## spin infra (terraform apply) + assets (bundle deploy)
	$(PY) -m accelerator.cli deploy code_migration

destroy:                 ## tear everything down (stops billing)
	$(PY) -m accelerator.cli destroy code_migration

dryrun: data test        ## offline validation of the build

clean:
	rm -rf usecases/code_migration/data/raw usecases/code_migration/data/sample \
	       usecases/code_migration/converted .runs metastore_db derby.log spark-warehouse

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'
