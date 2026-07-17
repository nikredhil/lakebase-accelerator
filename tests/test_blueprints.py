"""Unit tests for the blueprint metadata + SQL loader (no credentials)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import blueprints  # noqa: E402
import service  # noqa: E402


def test_backbone_blueprint_present():
    bp = blueprints.get_blueprint("stateful-agent-backbone")
    assert bp is not None
    assert bp["capacity"] == "CU_1"
    assert bp["usecase"] == "agent-backbone"
    assert len(bp["value_props"]) == 3
    assert len(bp["differentiation"]) == 3


def test_load_sql_modules_includes_agent_ddl():
    sql = blueprints.agent_schema_sql()
    assert "create schema if not exists agent" in sql
    assert "agent.interactions" in sql
    assert "vector(1024)" in sql  # pgvector memory column


def test_deploy_opts_carry_tags():
    bp = blueprints.get_blueprint("stateful-agent-backbone")
    opts = blueprints.deploy_opts(bp, "ml-platform")
    assert opts["capacity"] == "CU_1"
    assert opts["custom_tags"]["blueprint"] == "stateful-agent-backbone"
    assert opts["custom_tags"]["use_case"] == "stateful-agent-backbone"
    assert opts["custom_tags"]["cost_center"] == "ml-platform"


def test_deploy_opts_pass_through_build_instance():
    """The blueprint tags must survive service.build_instance untouched."""
    bp = blueprints.get_blueprint("stateful-agent-backbone")
    opts = blueprints.deploy_opts(bp, "cc-42")
    inst = service.build_instance(bp["usecase"], opts)
    tags = {t.key: t.value for t in inst.custom_tags}
    assert tags["blueprint"] == "stateful-agent-backbone"
    assert tags["cost_center"] == "cc-42"
    assert inst.name == "lakebase-agent-backbone"
    assert inst.capacity == "CU_1"


def test_empty_cost_center_omitted():
    bp = blueprints.get_blueprint("stateful-agent-backbone")
    opts = blueprints.deploy_opts(bp, "")
    assert "cost_center" not in opts["custom_tags"]
