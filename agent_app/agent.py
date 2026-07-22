"""In-app reference agent for the Stateful Agent Backbone.

Calls a Databricks Foundation Model serving endpoint for inference (pay-per-
token, scale-to-zero — no dedicated endpoint to stand up) and uses the deployed
Lakebase instance for memory:

  * short-term thread state  → agent.interactions (durable, eval-ready) +
    LangGraph checkpoint* tables (created by db.apply_schema for LangGraph-native
    agents to plug into).
  * long-term semantic memory → agent.memories (pgvector recall via bge-large-en).

Every turn writes a row to agent.interactions WITH cost_usd computed from token
counts, so the cost center's Agent bucket is the co-located governed ledger.
Branching clones a thread's memory under a new branch label for A/B / regression.
"""
from __future__ import annotations

import os
import time
import uuid
from contextlib import nullcontext

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

import db
import pricing

# MLflow tracing is best-effort: spans land in the experiment named by
# MLFLOW_EXPERIMENT (see app.yaml), but a missing wheel, an unreachable tracking
# server, or a permissions gap must never block or break chat.
try:
    import mlflow

    mlflow.set_tracking_uri("databricks")
    mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT", "/Shared/agent-backbone-traces"))
except Exception:
    mlflow = None


def _span(name: str, span_type: str):
    """An MLflow span context manager, or a no-op one when tracing is unavailable."""
    if mlflow is None:
        return nullcontext()
    try:
        return mlflow.start_span(name=name, span_type=span_type)
    except Exception:
        return nullcontext()


EMBED_ENDPOINT = "databricks-bge-large-en"
RECALL_K = 5
SYSTEM_PROMPT = (
    "You are a helpful assistant with persistent memory backed by Lakebase. "
    "Use the recalled memories when relevant. Be concise."
)


def list_models(w: WorkspaceClient) -> list[str]:
    """Chat-capable serving endpoints, friendliest first."""
    out = []
    try:
        for e in w.serving_endpoints.list():
            if getattr(e, "task", None) == "llm/v1/chat":
                out.append(e.name)
    except Exception:
        pass
    preferred = [m for m in ("databricks-claude-sonnet-4-5", "databricks-claude-haiku-4-5") if m in out]
    rest = [m for m in out if m not in preferred]
    return preferred + rest


def setup(w: WorkspaceClient, instance: str) -> dict:
    """Apply the agent schema modules + checkpointer to the instance."""
    return db.apply_schema(w, instance)


def list_threads(w: WorkspaceClient, instance: str) -> list[dict]:
    rows = db.query(
        w, instance,
        """select thread_id, branch, agent_id, agent_version, title, status,
                  last_active_at
           from agent.threads order by last_active_at desc limit 100""",
    )
    for r in rows:
        if r.get("last_active_at") is not None:
            r["last_active_at"] = str(r["last_active_at"])
    return rows


def get_thread(w: WorkspaceClient, instance: str, thread_id: str, branch: str = "main") -> list[dict]:
    rows = db.query(
        w, instance,
        """select turn_index, role, content, model, prompt_tokens, completion_tokens,
                  latency_ms, cost_usd, occurred_at
           from agent.interactions
           where thread_id = %s and branch = %s
           order by turn_index""",
        (thread_id, branch),
    )
    for r in rows:
        r["occurred_at"] = str(r.get("occurred_at"))
        if r.get("cost_usd") is not None:
            r["cost_usd"] = float(r["cost_usd"])
    return rows


def _embed(w: WorkspaceClient, text: str) -> str | None:
    """Return a pgvector literal '[...]' for the text, or None on failure."""
    try:
        r = w.serving_endpoints.query(name=EMBED_ENDPOINT, input=[text])
        vec = None
        data = getattr(r, "data", None)
        if data:
            first = data[0]
            vec = first.get("embedding") if isinstance(first, dict) else getattr(first, "embedding", None)
        if not vec:
            return None
        return "[" + ",".join(str(float(x)) for x in vec) + "]"
    except Exception:
        return None


def _recall(w: WorkspaceClient, instance: str, scope_id: str, qvec: str | None) -> list[str]:
    if not qvec:
        return []
    try:
        rows = db.query(
            w, instance,
            """select content from agent.memories
               where scope_id = %s and embedding is not null
               order by embedding <=> %s::vector limit %s""",
            (scope_id, qvec, RECALL_K),
        )
        return [r["content"] for r in rows]
    except Exception:
        return []


def _next_turn(w: WorkspaceClient, instance: str, thread_id: str, branch: str) -> int:
    rows = db.query(
        w, instance,
        "select coalesce(max(turn_index), -1) as m from agent.interactions where thread_id=%s and branch=%s",
        (thread_id, branch),
    )
    return int(rows[0]["m"]) + 1 if rows else 0


def chat(
    w: WorkspaceClient,
    instance: str,
    user_msg: str,
    thread_id: str | None = None,
    branch: str = "main",
    model: str = "databricks-claude-sonnet-4-5",
    agent_version: str = "v1",
    agent_id: str = "lakebase-app-agent",
    user_id: str = "app-user",
) -> dict:
    thread_id = thread_id or f"th_{uuid.uuid4().hex[:12]}"

    with _span("agent_chat", "AGENT") as root:
        try:
            if root:
                root.set_inputs({"message": user_msg, "thread_id": thread_id,
                                 "branch": branch, "model": model, "user_id": user_id})
        except Exception:
            pass

        history = get_thread(w, instance, thread_id, branch)
        with _span("embed_query", "EMBEDDING"):
            qvec = _embed(w, user_msg)
        with _span("memory_recall", "RETRIEVER") as recall_span:
            memories = _recall(w, instance, user_id, qvec)
            try:
                if recall_span:
                    recall_span.set_outputs({"memories": memories})
            except Exception:
                pass

        messages = [ChatMessage(role=ChatMessageRole.SYSTEM, content=SYSTEM_PROMPT)]
        if memories:
            messages.append(ChatMessage(
                role=ChatMessageRole.SYSTEM,
                content="Recalled memories:\n- " + "\n- ".join(memories),
            ))
        for h in history:
            role = ChatMessageRole.ASSISTANT if h["role"] == "assistant" else ChatMessageRole.USER
            messages.append(ChatMessage(role=role, content=h["content"] or ""))
        messages.append(ChatMessage(role=ChatMessageRole.USER, content=user_msg))

        t0 = time.time()
        with _span("llm_call", "LLM") as llm_span:
            resp = w.serving_endpoints.query(name=model, messages=messages)
            latency_ms = int((time.time() - t0) * 1000)
            reply = resp.choices[0].message.content if resp.choices else ""
            usage = resp.usage
            in_tok = int(getattr(usage, "prompt_tokens", 0) or 0)
            out_tok = int(getattr(usage, "completion_tokens", 0) or 0)
            try:
                if llm_span:
                    llm_span.set_attributes({"model": model, "prompt_tokens": in_tok,
                                             "completion_tokens": out_tok, "latency_ms": latency_ms})
            except Exception:
                pass
        cost_usd = pricing.token_cost(model, in_tok, out_tok)

        turn = _next_turn(w, instance, thread_id, branch)
        _persist_turn(w, instance, thread_id, branch, turn, "user", user_msg, model,
                      agent_version, None, None, None, None, user_id, qvec, agent_id)
        _persist_turn(w, instance, thread_id, branch, turn + 1, "assistant", reply, model,
                      agent_version, in_tok, out_tok, latency_ms, cost_usd, user_id, None, agent_id)

        try:
            if root:
                root.set_outputs({"reply": reply, "prompt_tokens": in_tok,
                                  "completion_tokens": out_tok, "cost_usd": cost_usd})
        except Exception:
            pass

    return {
        "thread_id": thread_id,
        "branch": branch,
        "model": model,
        "reply": reply,
        "prompt_tokens": in_tok,
        "completion_tokens": out_tok,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
    }


def _persist_turn(w, instance, thread_id, branch, turn, role, content, model,
                  agent_version, in_tok, out_tok, latency_ms, cost_usd, user_id, qvec,
                  agent_id="lakebase-app-agent"):
    with db.connect(w, instance) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """insert into agent.threads (thread_id, user_id, agent_id, agent_version, branch, last_active_at)
                   values (%s,%s,%s,%s,%s, now())
                   on conflict (thread_id) do update set last_active_at = now(),
                       agent_version = excluded.agent_version""",
                (thread_id, user_id, agent_id, agent_version, branch),
            )
            cur.execute(
                """insert into agent.interactions
                     (thread_id, turn_index, role, content, model, agent_version, branch,
                      prompt_tokens, completion_tokens, latency_ms, cost_usd)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (thread_id, turn, role, content, model, agent_version, branch,
                 in_tok, out_tok, latency_ms, cost_usd),
            )
            # Store the user's message as an episodic memory for future recall.
            if role == "user" and qvec:
                cur.execute(
                    """insert into agent.memories (scope, scope_id, kind, content, embedding, source_thread_id)
                       values ('user', %s, 'episodic', %s, %s::vector, %s)""",
                    (user_id, content, qvec, thread_id),
                )


def branch_thread(
    w: WorkspaceClient, instance: str, thread_id: str, new_branch: str, source_branch: str = "main"
) -> dict:
    """Clone a thread's interactions + memories under a new branch for A/B."""
    with db.connect(w, instance) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """insert into agent.threads (thread_id, user_id, agent_id, agent_version, branch, title)
                   select thread_id, user_id, agent_id, agent_version, %s,
                          coalesce(title,'') || ' (' || %s || ')'
                   from agent.threads where thread_id = %s
                   on conflict (thread_id) do nothing""",
                (new_branch, new_branch, thread_id),
            )
            cur.execute(
                """insert into agent.interactions
                     (thread_id, turn_index, role, content, model, agent_version, branch,
                      prompt_tokens, completion_tokens, latency_ms, cost_usd)
                   select thread_id, turn_index, role, content, model, agent_version, %s,
                          prompt_tokens, completion_tokens, latency_ms, cost_usd
                   from agent.interactions where thread_id = %s and branch = %s""",
                (new_branch, thread_id, source_branch),
            )
            cur.execute(
                """insert into agent.memories
                     (scope, scope_id, kind, content, embedding, source_thread_id, metadata)
                   select scope, scope_id, kind, content, embedding, source_thread_id,
                          jsonb_set(metadata, '{branch}', to_jsonb(%s::text))
                   from agent.memories where source_thread_id = %s""",
                (new_branch, thread_id),
            )
    return {"thread_id": thread_id, "branch": new_branch, "from": source_branch}


def cost_summary(w: WorkspaceClient, instance: str, days: int = 30) -> dict:
    """Aggregate the agent.interactions cost ledger for the cost center."""
    return db.agent_ledger(w, instance, days)
