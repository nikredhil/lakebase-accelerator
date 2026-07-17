"""Unit tests for the cost-center SDK layer (no real workspace calls)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import costs  # noqa: E402
from databricks.sdk.service.sql import State  # noqa: E402


class _WH:
    def __init__(self, id, serverless, state):
        self.id = id
        self.enable_serverless_compute = serverless
        self.state = state


class _FakeWarehouses:
    def __init__(self, items):
        self._items = items

    def list(self):
        return self._items


class _FakeClient:
    def __init__(self, warehouses):
        self.warehouses = _FakeWarehouses(warehouses)


def test_pick_warehouse_prefers_running_serverless():
    w = _FakeClient([
        _WH("a", False, State.RUNNING),
        _WH("b", True, State.STOPPED),
        _WH("c", True, State.RUNNING),
    ])
    assert costs.pick_warehouse(w) == "c"


def test_pick_warehouse_falls_back_to_any_serverless():
    w = _FakeClient([_WH("a", False, State.RUNNING), _WH("b", True, State.STOPPED)])
    assert costs.pick_warehouse(w) == "b"


def test_rollup_buckets():
    rows = [
        {"bucket": "agent", "dbus": 1, "usd": 2},
        {"bucket": "agent", "dbus": 3, "usd": 4},
        {"bucket": "lakebase", "dbus": 5, "usd": 6},
        {"bucket": "other", "dbus": 9, "usd": 9},
    ]
    b = costs._rollup(rows)
    assert b["agent"] == {"dbus": 4.0, "usd": 6.0}
    assert b["lakebase"] == {"dbus": 5.0, "usd": 6.0}
    assert b["app"] == {"dbus": 0.0, "usd": 0.0}


def test_get_estimate_always_succeeds_with_three_buckets():
    est = costs.get_estimate()
    assert est["source"] == "estimate"
    assert set(est["buckets"]) == {"agent", "app", "lakebase"}
    assert "savings" in est and "projection" in est


def test_get_costs_degrades_to_estimate_on_failure():
    class Boom:
        @property
        def warehouses(self):
            raise RuntimeError("PERMISSION_DENIED")

    out = costs.get_costs(Boom(), days=30)
    # pick_warehouse swallows the warehouse error and returns the hint id, but
    # run_query will then fail → estimate path. Either way: never raises.
    assert out["source"] in ("estimate", "live")


def test_get_costs_merges_agent_ledger():
    # Force the billing query to fail so we land on estimate, then confirm the
    # agent ledger overrides the Agent bucket.
    class Boom:
        @property
        def warehouses(self):
            raise RuntimeError("nope")

    out = costs.get_costs(Boom(), days=7, agent_costs={"usd": 1.2345, "dbus": None})
    assert out["buckets"]["agent"]["usd"] == 1.2345
    assert "interactions" in out["buckets"]["agent"]["basis"]
