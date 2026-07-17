"""Unit tests for the cost-center pricing model (no credentials needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import pricing  # noqa: E402


def test_dbu_to_usd():
    assert pricing.dbu_to_usd(10, 0.5) == 5.0
    assert pricing.dbu_to_usd(0) == 0.0


def test_token_cost_sonnet_vs_haiku():
    sonnet = pricing.token_cost("databricks-claude-sonnet-4-5", 1_000_000, 1_000_000)
    haiku = pricing.token_cost("databricks-claude-haiku-4-5", 1_000_000, 1_000_000)
    # Haiku is cheaper per token than Sonnet.
    assert haiku < sonnet
    # Sonnet: (42.857 + 214.286) DBU * $0.07
    assert round(sonnet, 4) == round((42.857 + 214.286) * pricing.MODEL_SERVING_USD_PER_DBU, 4)


def test_token_cost_unknown_model_uses_default():
    c = pricing.token_cost("databricks-some-new-model", 1_000_000, 0)
    assert c == pricing.token_cost("DEFAULT-anything", 1_000_000, 0)


def test_lakebase_monthly_scales_with_cu_and_hours():
    one = pricing.lakebase_monthly_usd(1, 8, 0.5)
    two = pricing.lakebase_monthly_usd(2, 8, 0.5)
    assert round(two, 4) == round(2 * one, 4)


def test_apps_monthly_medium_vs_large():
    med = pricing.apps_monthly_usd("MEDIUM", 24, 0.5)
    lrg = pricing.apps_monthly_usd("LARGE", 24, 0.5)
    assert lrg == 2 * med


def test_savings_math():
    s = pricing.savings({"a": 100, "b": 100}, 40)
    assert s["diy_total"] == 200.0
    assert s["lakebase_total"] == 40.0
    assert s["delta"] == 160.0
    assert s["pct"] == 80.0


def test_savings_zero_diy_guard():
    s = pricing.savings({}, 10)
    assert s["diy_total"] == 0.0
    assert s["pct"] == 0.0


def test_projection_has_three_buckets_and_savings():
    p = pricing.projection()
    for k in ("agent", "app", "lakebase", "total", "savings", "assumptions"):
        assert k in p
    assert p["total"] == round(p["agent"] + p["app"] + p["lakebase"], 2)
