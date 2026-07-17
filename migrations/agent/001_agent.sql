-- agent/001_agent.sql — Stateful Agent Backbone: long-term memory + governed eval loop.
-- Opt-in module (manifest: schema.modules includes "agent"). Requires pgcrypto + vector
-- (created in meta/000_prelude.sql).
--
-- Scope split:
--   * SHORT-TERM thread state (checkpoints) is owned by LangGraph's
--     `langgraph-checkpoint-postgres` checkpointer, which creates and migrates its own
--     tables via `checkpointer.setup()` (checkpoints, checkpoint_blobs, checkpoint_writes).
--     Do NOT recreate those here — this module is the application/eval layer around them.
--   * LONG-TERM memory, the append-only interaction log, eval feedback, and run metadata
--     live in the `agent` schema below.
--
-- Governed eval loop: every row in agent.interactions is the zero-ETL sync target to Delta
-- (register this Lakebase database in Unity Catalog and sync the schema) so eval,
-- fine-tuning, and analytics run on the lakehouse with no pipelines. Copy-on-write
-- branching of the instance gives isolated memory sandboxes for A/B and regression.

create schema if not exists agent;

-- Conversation thread registry (one row per LangGraph thread_id; branch-aware).
create table if not exists agent.threads (
  thread_id      text primary key,                  -- LangGraph thread id
  tenant_id      uuid not null default '00000000-0000-0000-0000-000000000000',
  user_id        text,
  agent_id       text not null,
  agent_version  text,
  branch         text not null default 'main',       -- memory-sandbox / eval branch label
  status         text not null default 'active',      -- active | resolved | archived
  title          text,
  metadata       jsonb not null default '{}'::jsonb,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  last_active_at timestamptz not null default now()
);
create index if not exists ix_threads_user  on agent.threads (tenant_id, user_id);
create index if not exists ix_threads_agent on agent.threads (agent_id, agent_version);

drop trigger if exists trg_threads_touch on agent.threads;
create trigger trg_threads_touch before update on agent.threads
  for each row execute function lakebase_meta.touch_updated_at();

-- Append-only interaction log — the eval / fine-tuning record. One row per turn.
-- This is the table you zero-ETL sync to Delta for offline eval and analytics.
create table if not exists agent.interactions (
  id                uuid not null default gen_random_uuid(),
  tenant_id         uuid not null default '00000000-0000-0000-0000-000000000000',
  thread_id         text not null,
  turn_index        int  not null,
  role              text not null,                    -- user | assistant | tool | system
  content           text,
  tool_calls        jsonb not null default '[]'::jsonb,
  model             text,
  agent_version     text,
  branch            text not null default 'main',
  prompt_tokens     int,
  completion_tokens int,
  latency_ms        int,
  cost_usd          numeric(10,4),
  metadata          jsonb not null default '{}'::jsonb,
  occurred_at       timestamptz not null default now(),
  primary key (id, occurred_at)
) partition by range (occurred_at);
create table if not exists agent.interactions_default partition of agent.interactions default;
create index if not exists ix_interactions_thread on agent.interactions (thread_id, turn_index);
create index if not exists ix_interactions_time   on agent.interactions using brin (occurred_at);
create index if not exists ix_interactions_eval   on agent.interactions (agent_version, branch);

-- Long-term semantic memory (facts, preferences, summaries) with vector recall.
create table if not exists agent.memories (
  id             uuid primary key default gen_random_uuid(),
  tenant_id      uuid not null default '00000000-0000-0000-0000-000000000000',
  scope          text not null default 'user',        -- user | agent | org
  scope_id       text not null,                        -- e.g. user_id or agent_id
  kind           text not null default 'fact',         -- fact | preference | summary | episodic
  content        text not null,
  embedding      vector(1024),                          -- dim must match the manifest model
  salience       real not null default 0.5,
  source_thread_id text,
  use_count      int not null default 0,
  metadata       jsonb not null default '{}'::jsonb,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  last_used_at   timestamptz,
  expires_at     timestamptz
);
create index if not exists ix_memories_scope on agent.memories (tenant_id, scope, scope_id);
create index if not exists ix_memories_meta  on agent.memories using gin (metadata jsonb_path_ops);
-- HNSW for cosine recall; build after first bulk load for large memory stores.
create index if not exists ix_memories_embedding
  on agent.memories using hnsw (embedding vector_cosine_ops);

drop trigger if exists trg_memories_touch on agent.memories;
create trigger trg_memories_touch before update on agent.memories
  for each row execute function lakebase_meta.touch_updated_at();

-- Eval feedback tied to a specific interaction (user thumbs, LLM-judge, human review).
create table if not exists agent.feedback (
  id             uuid primary key default gen_random_uuid(),
  tenant_id      uuid not null default '00000000-0000-0000-0000-000000000000',
  interaction_id uuid,
  thread_id      text,
  source         text not null default 'user',         -- user | llm_judge | human_review
  rating         int,                                   -- e.g. -1 / 0 / 1, or 1..5
  label          text,                                  -- e.g. 'hallucination','resolved'
  rationale      text,
  metadata       jsonb not null default '{}'::jsonb,
  created_at     timestamptz not null default now()
);
create index if not exists ix_feedback_interaction on agent.feedback (interaction_id);

-- Eval / regression run metadata (one row per run, typically against a branch).
create table if not exists agent.eval_runs (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null default '00000000-0000-0000-0000-000000000000',
  name          text not null,
  branch        text not null default 'main',
  agent_version text,
  dataset       text,
  status        text not null default 'running',        -- running | ok | failed
  metrics       jsonb not null default '{}'::jsonb,      -- aggregate scores
  started_at    timestamptz not null default now(),
  finished_at   timestamptz
);
create index if not exists ix_eval_runs_branch on agent.eval_runs (agent_version, branch);
