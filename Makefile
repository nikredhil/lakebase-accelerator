.PHONY: install plan deploy destroy list help
PY ?= python3
# Pass a use case: make deploy NAME=code_migration VARS=/path/to.tfvars BUNDLE=/path/to/bundle
NAME   ?= example
VARS   ?= infra/terraform/usecases/example.tfvars
BUNDLE ?=

install:
	$(PY) -m pip install -r requirements.txt

plan:
	$(PY) -m accelerator.cli plan $(NAME) --vars $(VARS) $(if $(BUNDLE),--bundle $(BUNDLE),)

deploy:
	$(PY) -m accelerator.cli deploy $(NAME) --vars $(VARS) $(if $(BUNDLE),--bundle $(BUNDLE),)

destroy:
	$(PY) -m accelerator.cli destroy $(NAME) --vars $(VARS) $(if $(BUNDLE),--bundle $(BUNDLE),)

list:
	$(PY) -m accelerator.cli list

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "};{printf "  %-10s %s\n",$$1,$$2}'
