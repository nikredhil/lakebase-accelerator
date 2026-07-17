"""Unit tests for accelerator/dab.py — no credentials needed."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from accelerator.config import Settings, DEFAULT_NODE_TYPES
from accelerator.dab import (
    _resolve_node_type,
    _build_cluster_resource,
    _build_schema_resource,
    _render_bundle_yaml,
)


# ---------------------------------------------------------------------------
# _resolve_node_type
# ---------------------------------------------------------------------------

class TestResolveNodeType:
    def test_aws_default(self):
        assert _resolve_node_type("aws", "") == "m5d.large"

    def test_azure_default(self):
        assert _resolve_node_type("azure", "") == "Standard_D4s_v3"

    def test_gcp_default(self):
        assert _resolve_node_type("gcp", "") == "n2-standard-4"

    def test_override_wins(self):
        assert _resolve_node_type("aws", "i3.xlarge") == "i3.xlarge"

    def test_unknown_cloud_falls_back_to_aws(self):
        assert _resolve_node_type("unknown", "") == "m5d.large"


# ---------------------------------------------------------------------------
# _build_cluster_resource
# ---------------------------------------------------------------------------

class TestBuildCluster:
    def _settings(self, **kw) -> Settings:
        defaults = dict(
            databricks_host="https://test.databricks.net",
            databricks_token="dapi_test",
            cloud="azure",
            max_workers=2,
            min_workers=1,
            spark_version="15.4.x-scala2.12",
            node_type_id="",
            use_spot=True,
            single_node=False,
            autotermination_minutes=20,
            create_schema=False,
            catalog_name="main",
            custom_tags={},
        )
        defaults.update(kw)
        return Settings(**defaults)

    def test_basic_cluster(self):
        c = _build_cluster_resource("myuc", self._settings())
        assert c["cluster_name"] == "lakebase-myuc-cluster"
        assert c["data_security_mode"] == "SINGLE_USER"
        assert c["node_type_id"] == "Standard_D4s_v3"
        assert c["custom_tags"]["usecase"] == "myuc"
        assert c["custom_tags"]["project"] == "lakebase-accelerator"
        assert c["custom_tags"]["managed"] == "dab"

    def test_autoscale(self):
        c = _build_cluster_resource("x", self._settings())
        assert "autoscale" in c
        assert c["autoscale"]["min_workers"] == 1
        assert c["autoscale"]["max_workers"] == 2
        assert "num_workers" not in c

    def test_single_node(self):
        c = _build_cluster_resource("x", self._settings(single_node=True))
        assert c["num_workers"] == 0
        assert "autoscale" not in c
        assert c["spark_conf"]["spark.master"] == "local[*]"
        assert c["custom_tags"]["ResourceClass"] == "SingleNode"

    def test_spot_azure(self):
        c = _build_cluster_resource("x", self._settings(cloud="azure", use_spot=True))
        assert "azure_attributes" in c
        assert c["azure_attributes"]["availability"] == "SPOT_WITH_FALLBACK_AZURE"
        assert "aws_attributes" not in c

    def test_spot_aws(self):
        c = _build_cluster_resource("x", self._settings(cloud="aws", use_spot=True))
        assert "aws_attributes" in c
        assert c["aws_attributes"]["availability"] == "SPOT_WITH_FALLBACK"
        assert "azure_attributes" not in c

    def test_spot_gcp(self):
        c = _build_cluster_resource("x", self._settings(cloud="gcp", use_spot=True))
        assert "gcp_attributes" in c

    def test_no_spot(self):
        c = _build_cluster_resource("x", self._settings(use_spot=False))
        assert "azure_attributes" not in c
        assert "aws_attributes" not in c
        assert "gcp_attributes" not in c

    def test_custom_tags_merged(self):
        c = _build_cluster_resource(
            "x", self._settings(custom_tags={"team": "data"}),
            extra_tags={"env": "prod"},
        )
        assert c["custom_tags"]["team"] == "data"
        assert c["custom_tags"]["env"] == "prod"
        assert c["custom_tags"]["project"] == "lakebase-accelerator"

    def test_max_workers_guardrail(self):
        with pytest.raises(ValueError, match="max_workers must be <= 2"):
            _build_cluster_resource("x", self._settings(max_workers=5))


# ---------------------------------------------------------------------------
# _build_schema_resource
# ---------------------------------------------------------------------------

class TestBuildSchema:
    def test_schema_disabled(self):
        s = Settings(
            databricks_host="", databricks_token="", cloud="aws",
            max_workers=2, min_workers=1, spark_version="15.4.x-scala2.12",
            node_type_id="", use_spot=True, single_node=False,
            autotermination_minutes=20, create_schema=False,
            catalog_name="main", custom_tags={},
        )
        assert _build_schema_resource("x", s) is None

    def test_schema_enabled(self):
        s = Settings(
            databricks_host="", databricks_token="", cloud="aws",
            max_workers=2, min_workers=1, spark_version="15.4.x-scala2.12",
            node_type_id="", use_spot=True, single_node=False,
            autotermination_minutes=20, create_schema=True,
            catalog_name="analytics", custom_tags={},
        )
        schema = _build_schema_resource("myuc", s)
        assert schema["catalog_name"] == "analytics"
        assert schema["name"] == "lakebase_myuc"


# ---------------------------------------------------------------------------
# _render_bundle_yaml
# ---------------------------------------------------------------------------

class TestRenderBundle:
    def test_generates_valid_yaml(self, tmp_path):
        s = Settings(
            databricks_host="", databricks_token="", cloud="azure",
            max_workers=2, min_workers=1, spark_version="15.4.x-scala2.12",
            node_type_id="", use_spot=True, single_node=False,
            autotermination_minutes=20, create_schema=False,
            catalog_name="main", custom_tags={},
        )
        with patch("accelerator.dab.WORKSPACES_DIR", tmp_path):
            ws_dir = _render_bundle_yaml("testuc", s, "dev")

        yml = yaml.safe_load((ws_dir / "databricks.yml").read_text())
        assert yml["bundle"]["name"] == "lakebase-testuc"
        assert "lakebase_cluster" in yml["resources"]["clusters"]
        cluster = yml["resources"]["clusters"]["lakebase_cluster"]
        assert cluster["cluster_name"] == "lakebase-testuc-cluster"
        assert cluster["azure_attributes"]["availability"] == "SPOT_WITH_FALLBACK_AZURE"

    def test_single_node_yaml(self, tmp_path):
        s = Settings(
            databricks_host="", databricks_token="", cloud="aws",
            max_workers=2, min_workers=1, spark_version="15.4.x-scala2.12",
            node_type_id="", use_spot=False, single_node=True,
            autotermination_minutes=10, create_schema=False,
            catalog_name="main", custom_tags={},
        )
        with patch("accelerator.dab.WORKSPACES_DIR", tmp_path):
            ws_dir = _render_bundle_yaml("sn_test", s, "dev")

        yml = yaml.safe_load((ws_dir / "databricks.yml").read_text())
        cluster = yml["resources"]["clusters"]["lakebase_cluster"]
        assert cluster["num_workers"] == 0
        assert "autoscale" not in cluster

    def test_schema_included_when_enabled(self, tmp_path):
        s = Settings(
            databricks_host="", databricks_token="", cloud="aws",
            max_workers=2, min_workers=1, spark_version="15.4.x-scala2.12",
            node_type_id="", use_spot=False, single_node=False,
            autotermination_minutes=20, create_schema=True,
            catalog_name="main", custom_tags={},
        )
        with patch("accelerator.dab.WORKSPACES_DIR", tmp_path):
            ws_dir = _render_bundle_yaml("schema_test", s, "dev")

        yml = yaml.safe_load((ws_dir / "databricks.yml").read_text())
        assert "schemas" in yml["resources"]
        assert yml["resources"]["schemas"]["lakebase_schema"]["name"] == "lakebase_schema_test"
