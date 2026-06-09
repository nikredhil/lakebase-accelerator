"""Unit tests for accelerator/config.py."""
from accelerator.config import Settings, _parse_tags, DEFAULT_NODE_TYPES


class TestParseTags:
    def test_empty(self):
        assert _parse_tags("") == {}

    def test_kv_pairs(self):
        assert _parse_tags("team=data,cost_center=1234") == {
            "team": "data",
            "cost_center": "1234",
        }

    def test_json(self):
        assert _parse_tags('{"team": "data"}') == {"team": "data"}

    def test_whitespace(self):
        assert _parse_tags(" team = data , env = prod ") == {
            "team": "data",
            "env": "prod",
        }


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.cloud in ("aws", "azure", "gcp", "")
        assert s.max_workers >= 1


class TestNodeTypeDefaults:
    def test_all_clouds_have_defaults(self):
        for cloud in ("aws", "azure", "gcp"):
            assert cloud in DEFAULT_NODE_TYPES
