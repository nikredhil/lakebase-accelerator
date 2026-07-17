"""Unit tests for the Databricks App service layer (no credentials needed)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from service import build_instance, detect_cloud, instance_name  # noqa: E402


def test_instance_name_slug():
    assert instance_name("code_migration") == "lakebase-code-migration"
    assert instance_name("ETL") == "lakebase-etl"


def test_default_instance():
    inst = build_instance("demo", {})
    assert inst.name == "lakebase-demo"
    assert inst.capacity == "CU_1"
    tags = {t.key: t.value for t in inst.custom_tags}
    # collision-proof key: workspace default-tag policies can own 'project'
    assert tags["lakebase_project"] == "lakebase-accelerator"
    assert "project" not in tags
    assert tags["usecase"] == "demo"


def test_custom_tags_and_retention():
    inst = build_instance("x", {"custom_tags": {"team": "data"}, "retention_days": 14})
    tags = {t.key: t.value for t in inst.custom_tags}
    assert tags["team"] == "data"
    assert inst.retention_window_in_days == 14


def test_capacity_guardrail():
    assert build_instance("x", {"capacity": "CU_2"}).capacity == "CU_2"
    with pytest.raises(ValueError, match="cost guardrail"):
        build_instance("x", {"capacity": "CU_4"})


def test_retention_bounds():
    with pytest.raises(ValueError, match="retention_days"):
        build_instance("x", {"retention_days": 60})


def test_bad_usecase_name():
    with pytest.raises(ValueError):
        build_instance("bad name!", {})


def test_detect_cloud():
    assert detect_cloud("https://adb-123.8.azuredatabricks.net") == "azure"
    assert detect_cloud("https://x.gcp.databricks.com") == "gcp"
    assert detect_cloud("https://dbc-1.cloud.databricks.com") == "aws"
