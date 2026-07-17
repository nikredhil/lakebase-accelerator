-- core/001_core.sql — universal flexible model: entities, relationships, events, tags.
create schema if not exists core;

-- Typed entity with JSONB attributes + generated full-text search vector.
create table if not exists core.entities (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null default '00000000-0000-0000-0000-000000000000',
  entity_type text not null,                      -- e.g. 'customer','asset','order'
  natural_key text,                               -- caller's stable id (dedupe)
  attributes  jsonb not null default '{}'::jsonb, -- the variable 80%
  search_tsv  tsvector generated always as (
                to_tsvector('simple',
                  coalesce(natural_key,'') || ' ' || coalesce(attributes::text,''))
              ) stored,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  created_by  text,
  updated_by  text,
  metadata    jsonb not null default '{}'::jsonb,
  deleted_at  timestamptz,
  unique (tenant_id, entity_type, natural_key)
);
create index if not exists ix_entities_type   on core.entities (tenant_id, entity_type);
create index if not exists ix_entities_attrs  on core.entities using gin (attributes jsonb_path_ops);
create index if not exists ix_entities_search on core.entities using gin (search_tsv);

drop trigger if exists trg_entities_touch on core.entities;
create trigger trg_entities_touch before update on core.entities
  for each row execute function lakebase_meta.touch_updated_at();

-- Typed edges between entities (graph-like).
create table if not exists core.relationships (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null default '00000000-0000-0000-0000-000000000000',
  from_id    uuid not null references core.entities(id) on delete cascade,
  to_id      uuid not null references core.entities(id) on delete cascade,
  rel_type   text not null,                       -- e.g. 'owns','located_at'
  attributes jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (tenant_id, from_id, to_id, rel_type)
);
create index if not exists ix_rel_from on core.relationships (from_id, rel_type);
create index if not exists ix_rel_to   on core.relationships (to_id, rel_type);

-- Append-only event log / time-series (partition by range; add monthly partitions in prod).
create table if not exists core.events (
  id          uuid not null default gen_random_uuid(),
  tenant_id   uuid not null default '00000000-0000-0000-0000-000000000000',
  entity_id   uuid,
  event_type  text not null,
  payload     jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now(),
  primary key (id, occurred_at)
) partition by range (occurred_at);
create table if not exists core.events_default partition of core.events default;
create index if not exists ix_events_entity on core.events (entity_id, occurred_at);
create index if not exists ix_events_time   on core.events using brin (occurred_at);

create table if not exists core.tags (
  entity_id uuid not null references core.entities(id) on delete cascade,
  key       text not null,
  value     text,
  primary key (entity_id, key)
);
