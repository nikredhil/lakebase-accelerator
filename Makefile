.PHONY: install plan deploy destroy status list test test-e2e help sync-agent-app
PY ?= python3
NAME   ?= example
TARGET ?= dev
VARS   ?=
TAGS   ?=

install:
	$(PY) -m pip install -r requirements.txt

# Keep the agent backbone app's copies of the shared modules in sync with the
# control-plane app (Databricks Apps deploy one source tree per app).
sync-agent-app:
	cp app/service.py app/pricing.py app/blueprints.py app/db.py agent_app/
	cp app/sql/*.sql app/sql/README.md agent_app/sql/
	@echo "synced shared modules into agent_app/ (agent.py is owned by agent_app)"

plan:
	$(PY) -m accelerator.cli plan $(NAME) --target $(TARGET) $(if $(VARS),--vars-file $(VARS),) $(if $(TAGS),--tags $(TAGS),)

deploy:
	$(PY) -m accelerator.cli deploy $(NAME) --target $(TARGET) $(if $(VARS),--vars-file $(VARS),) $(if $(TAGS),--tags $(TAGS),)

destroy:
	$(PY) -m accelerator.cli destroy $(NAME) --target $(TARGET)

status:
	$(PY) -m accelerator.cli status $(NAME) --target $(TARGET)

list:
	$(PY) -m accelerator.cli list

test:
	$(PY) -m pytest tests/ -v --ignore=tests/test_e2e.py

test-e2e:
	$(PY) -m pytest tests/test_e2e.py -v --e2e

help:
	@echo "  install   Install Python dependencies"
	@echo "  plan      Validate use-case bundle (NAME=x [VARS=f.json] [TAGS=k=v])"
	@echo "  deploy    Deploy use-case infra (NAME=x [VARS=f.json] [TAGS=k=v])"
	@echo "  destroy   Tear down use-case infra (NAME=x)"
	@echo "  status    Show use-case deployment status (NAME=x)"
	@echo "  list      List all deployed use cases"
	@echo "  test      Run unit tests"
	@echo "  test-e2e  Run end-to-end tests (needs DATABRICKS_HOST/TOKEN)"
