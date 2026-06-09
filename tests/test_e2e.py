"""End-to-end tests — requires DATABRICKS_HOST/TOKEN credentials.

Run with: pytest tests/test_e2e.py --e2e -v
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

USECASE = "e2e_test"


@pytest.fixture(autouse=True)
def cleanup():
    """Ensure the e2e use case is destroyed after each test."""
    yield
    try:
        from accelerator.cli import destroy
        destroy(USECASE, target="dev")
    except Exception:
        pass


def test_deploy_creates_cluster():
    """Deploy a single-node cluster (cheapest) and verify it exists."""
    from accelerator.cli import deploy
    from databricks.sdk import WorkspaceClient

    cluster_id = deploy(
        USECASE,
        target="dev",
        var_overrides={
            "single_node": True,
            "autotermination_minutes": 10,
        },
    )

    # Verify via SDK
    w = WorkspaceClient()
    clusters = list(w.clusters.list())
    matching = [c for c in clusters if f"lakebase-{USECASE}" in (c.cluster_name or "")]
    assert len(matching) >= 1, f"Expected a lakebase-{USECASE} cluster, found none"

    found = matching[0]
    tags = found.custom_tags or {}
    if isinstance(tags, dict):
        assert tags.get("project") == "lakebase-accelerator"
        assert tags.get("usecase") == USECASE


def test_destroy_removes_cluster():
    """Deploy then destroy, verify the cluster is gone."""
    from accelerator.cli import deploy, destroy
    from databricks.sdk import WorkspaceClient

    deploy(
        USECASE,
        target="dev",
        var_overrides={"single_node": True, "autotermination_minutes": 10},
    )

    destroy(USECASE, target="dev")

    w = WorkspaceClient()
    clusters = list(w.clusters.list())
    matching = [c for c in clusters if f"lakebase-{USECASE}" in (c.cluster_name or "")]
    assert len(matching) == 0, f"Expected cluster to be destroyed, but found: {matching}"


def test_deploy_with_custom_tags():
    """Deploy with custom tags and verify they appear on the cluster."""
    from accelerator.cli import deploy
    from databricks.sdk import WorkspaceClient

    deploy(
        USECASE,
        target="dev",
        var_overrides={"single_node": True, "autotermination_minutes": 10},
        extra_tags={"team": "test-team", "cost_center": "99999"},
    )

    w = WorkspaceClient()
    clusters = list(w.clusters.list())
    matching = [c for c in clusters if f"lakebase-{USECASE}" in (c.cluster_name or "")]
    assert len(matching) >= 1

    tags = matching[0].custom_tags or {}
    if isinstance(tags, dict):
        assert tags.get("team") == "test-team"
        assert tags.get("cost_center") == "99999"
