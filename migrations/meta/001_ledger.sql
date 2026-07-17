-- meta/001_ledger.sql — accelerator bookkeeping (migration ledger, modules, ingest runs).
create table if not exists lakebase_meta.schema_migrations (
  version    text not null,
  module     text not null,
  checksum   text not null,
  applied_at timestamptz not null default now(),
  primary key (module, version)
);

create table if not exists lakebase_meta.modules (
  module     text primary key,
  enabled_at timestamptz not null default now()
);

create table if not exists lakebase_meta.ingest_runs (
  id            uuid primary key default gen_random_uuid(),
  collection_id uuid,
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  docs_seen     int default 0,
  docs_embedded int default 0,
  model         text,
  status        text not null default 'running',  -- running | ok | failed
  error         text
);
