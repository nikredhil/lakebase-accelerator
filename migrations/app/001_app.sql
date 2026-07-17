-- app/001_app.sql — operational app baseline: users, sessions, audit_log, settings.
create schema if not exists app;

create table if not exists app.users (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null default '00000000-0000-0000-0000-000000000000',
  email        text not null,
  display_name text,
  attributes   jsonb not null default '{}'::jsonb,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  deleted_at   timestamptz,
  unique (tenant_id, email)
);
drop trigger if exists trg_users_touch on app.users;
create trigger trg_users_touch before update on app.users
  for each row execute function lakebase_meta.touch_updated_at();

create table if not exists app.sessions (
  id        uuid primary key default gen_random_uuid(),
  user_id   uuid references app.users(id) on delete cascade,
  issued_at timestamptz not null default now(),
  expires_at timestamptz,
  metadata  jsonb not null default '{}'::jsonb
);

create table if not exists app.audit_log (
  id        uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default '00000000-0000-0000-0000-000000000000',
  actor     text,
  action    text not null,
  target    text,
  detail    jsonb not null default '{}'::jsonb,
  at        timestamptz not null default now()
);

create table if not exists app.settings (
  tenant_id uuid not null default '00000000-0000-0000-0000-000000000000',
  key       text not null,
  value     jsonb not null default '{}'::jsonb,
  primary key (tenant_id, key)
);

-- Multi-tenant RLS — applied ONLY when schema.multi_tenant = true (see design-spec §8.2, §10.4).
-- The migrator emits these per tenant-scoped table when the flag is set:
--   alter table core.entities enable row level security;
--   create policy tenant_isolation on core.entities
--     using (tenant_id = current_setting('app.tenant_id', true)::uuid);
-- Clients then run:  set app.tenant_id = '<uuid>';  per session/transaction.
