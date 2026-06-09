"""LLM helpers.

`databricks_chat` calls a Databricks-hosted foundation model (e.g. Claude) via
Mosaic AI Model Serving — governed, no external API key, billed through the
workspace. Endpoint is configurable via DATABRICKS_LLM_ENDPOINT.
"""
from __future__ import annotations

import os

DEFAULT_ENDPOINT = "databricks-claude-opus-4-8"


def databricks_chat(system: str, user: str, max_tokens: int = 4000, endpoint: str | None = None) -> str:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

    w = WorkspaceClient()
    ep = endpoint or os.getenv("DATABRICKS_LLM_ENDPOINT", DEFAULT_ENDPOINT)
    resp = w.serving_endpoints.query(
        name=ep,
        messages=[
            ChatMessage(role=ChatMessageRole.SYSTEM, content=system),
            ChatMessage(role=ChatMessageRole.USER, content=user),
        ],
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""
