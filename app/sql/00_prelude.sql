-- meta/000_prelude.sql — extensions + shared helpers. Always applied first.
create extension if not exists pgcrypto;   -- gen_random_uuid()
create extension if not exists vector;     -- pgvector

create schema if not exists lakebase_meta;

-- updated_at maintenance, reused by every module's triggers.
create or replace function lakebase_meta.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;
