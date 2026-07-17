"""Lakebase Agent Backbone — Databricks App backend.

The live Stateful Agent Backbone: a chat app whose memory lives in a Lakebase
(Postgres) instance. Short-term thread state via the LangGraph
langgraph-checkpoint-postgres checkpointer; long-term semantic memory + an
append-only governed eval log (agent.interactions, with per-turn cost_usd) in
the `agent` schema. Branch a thread to A/B agent versions on isolated memory.

Runs as its own Databricks App (name: lakebase-agent-backbone), separate from
the control-plane app. Shares the service/pricing/blueprints/db/agent modules
(copied into this source dir, since Apps deploy a single source tree).

Auth: all workspace calls run as this app's service principal.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import blueprints
import service

app = FastAPI(title="Lakebase Agent Backbone")

STATIC_DIR = Path(__file__).parent / "static"
BACKBONE_USECASE = blueprints.BLUEPRINTS["stateful-agent-backbone"]["usecase"]

_sp_client: WorkspaceClient | None = None


def client() -> WorkspaceClient:
    global _sp_client
    if _sp_client is None:
        _sp_client = WorkspaceClient()
    return _sp_client


def _agent():
    import agent  # lazy: keeps the app booting if langgraph/psycopg fail to import
    return agent


class InstanceRequest(BaseModel):
    instance: str


class ChatRequest(BaseModel):
    instance: str
    message: str
    thread_id: str | None = None
    branch: str = "main"
    model: str = "databricks-claude-sonnet-4-5"


class BranchRequest(BaseModel):
    instance: str
    thread_id: str
    new_branch: str
    source_branch: str = "main"


@app.get("/api/config")
def get_config(request: Request) -> dict[str, Any]:
    w = client()
    # Surface backbone instances (deployed by the control plane) so the UI can
    # default to one without making the user hunt for the name.
    backbones, others = [], []
    try:
        for i in service.managed_instances(w):
            s = service.to_summary(w, i)
            (backbones if (s.get("tags") or {}).get("blueprint") == "stateful-agent-backbone" else others).append(s)
    except Exception:
        pass
    return {
        "host": w.config.host,
        "user": request.headers.get("x-forwarded-email", ""),
        "backbones": backbones,
        "others": others,
        "default_instance": (backbones or others or [{}])[0].get("name", ""),
    }


@app.get("/api/agent/models")
def agent_models() -> list[str]:
    try:
        return _agent().list_models(client())
    except Exception:
        return []


@app.post("/api/agent/setup")
def agent_setup(req: InstanceRequest) -> dict[str, Any]:
    try:
        return _agent().setup(client(), req.instance)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/agent/threads")
def agent_threads(instance: str) -> list[dict[str, Any]]:
    try:
        return _agent().list_threads(client(), instance)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/agent/thread")
def agent_thread(instance: str, thread_id: str, branch: str = "main") -> list[dict[str, Any]]:
    try:
        return _agent().get_thread(client(), instance, thread_id, branch)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/agent/chat")
def agent_chat(req: ChatRequest) -> dict[str, Any]:
    try:
        return _agent().chat(
            client(), req.instance, req.message,
            thread_id=req.thread_id, branch=req.branch, model=req.model,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/agent/branch")
def agent_branch(req: BranchRequest) -> dict[str, Any]:
    try:
        return _agent().branch_thread(
            client(), req.instance, req.thread_id, req.new_branch, req.source_branch,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/agent/cost")
def agent_cost(instance: str, days: int = 30) -> dict[str, Any]:
    """The agent's own per-turn cost ledger (from agent.interactions)."""
    try:
        import db
        return db.agent_ledger(client(), instance, days)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
