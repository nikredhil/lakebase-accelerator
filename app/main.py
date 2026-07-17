"""Lakebase Accelerator — Databricks App backend.

FastAPI server exposing the Lakebase control-plane operations (deploy /
destroy / start / stop / list database instances) over the databricks-sdk,
plus the static red & white UI.

Auth: all workspace calls run as the app's service principal (credentials are
injected by the Apps runtime). The default forwarded user token only carries
iam read scopes, so it cannot drive the database API.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import blueprints
import costs
import service

app = FastAPI(title="TwinOS Lakebase Deployer")

STATIC_DIR = Path(__file__).parent / "static"

_sp_client: WorkspaceClient | None = None


def client_for(request: Request) -> WorkspaceClient:
    global _sp_client
    if _sp_client is None:
        _sp_client = WorkspaceClient()
    return _sp_client


class DeployRequest(BaseModel):
    usecase: str = Field(min_length=1, max_length=31)
    capacity: str = "CU_1"
    retention_days: int | None = None
    custom_tags: dict[str, str] = Field(default_factory=dict)


class UsecaseRequest(BaseModel):
    usecase: str


class BlueprintDeployRequest(BaseModel):
    cost_center: str = ""


AGENT_APP_NAME = "lakebase-agent-backbone"


def _err(e: Exception) -> HTTPException:
    msg = str(e)
    code = 400 if isinstance(e, ValueError) else 502
    if "PERMISSION_DENIED" in msg or "permission" in msg.lower():
        msg += (
            " — the app's service principal may lack rights to manage "
            "database instances; grant it access in the workspace admin console."
        )
    return HTTPException(status_code=code, detail=msg)


@app.get("/api/config")
def get_config(request: Request) -> dict[str, Any]:
    w = client_for(request)
    agent_app_url = ""
    try:  # link out to the separate agent backbone app, if deployed
        agent_app_url = w.apps.get(AGENT_APP_NAME).url or ""
    except Exception:
        agent_app_url = ""
    return {
        "host": w.config.host,
        "cloud": service.detect_cloud(w.config.host or ""),
        "user": request.headers.get("x-forwarded-email", ""),
        "capacities": list(service.ALLOWED_CAPACITIES),
        "agent_app_url": agent_app_url,
    }


@app.get("/api/deployments")
def list_deployments(request: Request) -> list[dict[str, Any]]:
    w = client_for(request)
    try:
        return sorted(
            (service.to_summary(w, i) for i in service.managed_instances(w)),
            key=lambda d: d["usecase"],
        )
    except Exception as e:
        raise _err(e)


@app.post("/api/deploy")
def deploy(req: DeployRequest, request: Request) -> dict[str, Any]:
    w = client_for(request)
    try:
        return service.deploy(w, req.usecase, req.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise _err(e)


@app.post("/api/destroy")
def destroy(req: UsecaseRequest, request: Request) -> dict[str, Any]:
    w = client_for(request)
    try:
        return service.destroy(w, req.usecase)
    except Exception as e:
        raise _err(e)


@app.post("/api/instances/{name}/start")
def start_instance(name: str, request: Request) -> dict[str, str]:
    w = client_for(request)
    try:
        service.set_stopped(w, name, False)
        return {"status": "starting"}
    except Exception as e:
        raise _err(e)


@app.post("/api/instances/{name}/stop")
def stop_instance(name: str, request: Request) -> dict[str, str]:
    w = client_for(request)
    try:
        service.set_stopped(w, name, True)  # compute stops; data is retained
        return {"status": "stopping"}
    except Exception as e:
        raise _err(e)


# --------------------------------------------------------------------------- #
# Blueprints — packaged use cases (flagship: Stateful Agent Backbone)
# --------------------------------------------------------------------------- #
@app.get("/api/blueprints")
def list_blueprints() -> list[dict[str, Any]]:
    return list(blueprints.BLUEPRINTS.values())


@app.get("/api/blueprints/{slug}/schema")
def blueprint_schema(slug: str) -> dict[str, Any]:
    bp = blueprints.get_blueprint(slug)
    if not bp:
        raise HTTPException(status_code=404, detail=f"unknown blueprint '{slug}'")
    return {"sql": blueprints.agent_schema_sql()}


@app.post("/api/blueprints/{slug}/deploy")
def deploy_blueprint(slug: str, req: BlueprintDeployRequest, request: Request) -> dict[str, Any]:
    bp = blueprints.get_blueprint(slug)
    if not bp:
        raise HTTPException(status_code=404, detail=f"unknown blueprint '{slug}'")
    w = client_for(request)
    try:
        opts = blueprints.deploy_opts(bp, req.cost_center)
        return service.deploy(w, bp["usecase"], opts)
    except Exception as e:
        raise _err(e)


# --------------------------------------------------------------------------- #
# Cost center — DBU→$ across Agent / App / Lakebase (never 5xxes)
# --------------------------------------------------------------------------- #
@app.get("/api/costs")
def get_costs(request: Request, days: int = 30) -> dict[str, Any]:
    w = client_for(request)
    agent_costs = None
    # The Agent bucket is most precise from the co-located interaction log,
    # which lives in the backbone instance's Postgres (read via db.agent_ledger).
    inst = blueprints.BLUEPRINTS["stateful-agent-backbone"]["usecase"]
    try:
        if service.find_instance(w, inst):
            import db  # lazy: psycopg import only when a backbone exists
            agent_costs = db.agent_ledger(w, service.instance_name(inst), days)
    except Exception:
        agent_costs = None
    return costs.get_costs(w, days, agent_costs=agent_costs)


@app.get("/api/costs/estimate")
def get_costs_estimate(
    cu: int = 1, lakebase_hours_per_day: int = 8, apps_size: str = "MEDIUM",
    apps_hours_per_day: int = 24, agent_in_tokens_per_day: int = 0,
    agent_out_tokens_per_day: int = 0, agent_model: str = "claude-sonnet-4-5",
) -> dict[str, Any]:
    return costs.get_estimate({
        "cu": cu, "lakebase_hours_per_day": lakebase_hours_per_day,
        "apps_size": apps_size, "apps_hours_per_day": apps_hours_per_day,
        "agent_in_tokens_per_day": agent_in_tokens_per_day,
        "agent_out_tokens_per_day": agent_out_tokens_per_day,
        "agent_model": agent_model,
    })


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
