"""Solution blueprints — packaged use cases surfaced as one-click deploys.

Today there's one flagship: the Stateful Agent Backbone. A blueprint carries
the narrative shown in the UI plus the provisioning defaults (capacity, tags,
schema modules) so the app can deploy it via the existing service.deploy().
"""
from __future__ import annotations

import functools
from pathlib import Path

SQL_DIR = Path(__file__).parent / "sql"
# Local-dev fallback if the app is run from a checkout (not the deployed bundle).
MIGRATIONS_DIR = Path(__file__).parents[1] / "migrations"

README_URL = (
    "https://github.com/lakebase-accelerator/usecases/"
    "stateful-agent-backbone/README.md"
)

BLUEPRINTS = {
    "stateful-agent-backbone": {
        "slug": "stateful-agent-backbone",
        "name": "Stateful Agent Backbone",
        "tagline": "One governed store for agent memory + a zero-ETL eval loop.",
        "usecase": "agent-backbone",        # instance name → lakebase-agent-backbone
        "capacity": "CU_1",
        "schema_modules": ["meta", "core", "agent"],
        "tags": {
            "blueprint": "stateful-agent-backbone",
            "use_case": "stateful-agent-backbone",
        },
        "value_props": [
            "One governed store for short- and long-term memory — LangGraph "
            "langgraph-checkpoint-postgres checkpointer (thread state) + Lakebase "
            "(semantic memory in the agent schema).",
            "Zero-ETL eval/fine-tuning — every interaction lands in "
            "agent.interactions, synced to Delta, so quality measurement and "
            "training-data prep need no pipelines.",
            "Branch a memory state in seconds to A/B agent versions or run "
            "regression suites on an isolated copy. Consumption scales per session.",
        ],
        "differentiation": [
            {
                "vs": "DIY (Redis + Postgres + vector + eval pipeline)",
                "why": "Fragmented and ungoverned; you ETL just to measure quality. "
                       "Here it's one store, governed, zero-ETL.",
            },
            {
                "vs": "Standalone Neon / RDS",
                "why": "Memory isn't co-located with training data — you still pipe "
                       "traces to the lakehouse. Lakebase is co-located by design.",
            },
            {
                "vs": "Any other managed Postgres",
                "why": "Lakebase is the only one with copy-on-write data branching "
                       "for instant eval/memory sandboxes.",
            },
        ],
        "next_steps": [
            "Apply the agent schema module (threads, interactions, memories, "
            "feedback, eval_runs) — the app does this from the Agent tab.",
            "Wire the LangGraph checkpointer to this instance's Postgres endpoint.",
            "Register the instance in Unity Catalog and turn on zero-ETL sync of "
            "agent.interactions to Delta for eval and fine-tuning.",
        ],
        "readme_url": README_URL,
    }
}


def get_blueprint(slug: str) -> dict | None:
    return BLUEPRINTS.get(slug)


def deploy_opts(bp: dict, cost_center: str) -> dict:
    """Build the opts dict for service.deploy() from a blueprint + cost center."""
    tags = dict(bp["tags"])
    if cost_center:
        tags["cost_center"] = cost_center
    return {"capacity": bp["capacity"], "custom_tags": tags}


@functools.lru_cache(maxsize=1)
def load_sql_modules() -> list[tuple[str, str]]:
    """Return [(name, sql), ...] in apply order from the vendored app/sql dir.

    Falls back to the canonical migrations/ tree for local dev.
    """
    out: list[tuple[str, str]] = []
    if SQL_DIR.exists():
        for f in sorted(SQL_DIR.glob("*.sql")):
            out.append((f.name, f.read_text()))
    if out:
        return out
    # Fallback: assemble from the canonical migrations layout.
    for rel in (
        "meta/000_prelude.sql",
        "meta/001_ledger.sql",
        "core/001_core.sql",
        "agent/001_agent.sql",
    ):
        p = MIGRATIONS_DIR / rel
        if p.exists():
            out.append((rel, p.read_text()))
    return out


def agent_schema_sql() -> str:
    """The full DDL the app applies for the backbone (concatenated modules)."""
    return "\n\n".join(sql for _, sql in load_sql_modules())
