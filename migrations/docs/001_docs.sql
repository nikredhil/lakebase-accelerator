-- docs/001_docs.sql — unstructured / RAG: collections, documents, document_chunks.
-- Opt-in (manifest unstructured.enabled = true). Vector dim must match the collection's model.
create schema if not exists docs;

create table if not exists docs.collections (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null default '00000000-0000-0000-0000-000000000000',
  name            text not null,
  embedding_model text not null default 'databricks-bge-large-en',
  embedding_dim   int  not null default 1024,
  metadata        jsonb not null default '{}'::jsonb,
  created_at      timestamptz not null default now(),
  unique (tenant_id, name)
);

create table if not exists docs.documents (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null default '00000000-0000-0000-0000-000000000000',
  collection_id uuid references docs.collections(id) on delete cascade,
  external_id   text,                               -- caller id
  title         text,
  mime_type     text,
  byte_size     bigint,
  checksum      text not null,                      -- sha256, dedupe key
  storage_tier  text not null default 'inline',     -- inline | volume | external
  source_uri    text,                               -- /Volumes/... when not inline
  content_bytes bytea,                              -- small inline binaries
  content_text  text,                               -- extracted / plain text
  content_tsv   tsvector generated always as (
                  to_tsvector('simple', coalesce(content_text,''))
                ) stored,
  language      text,
  metadata      jsonb not null default '{}'::jsonb,
  ingest_status text not null default 'pending',    -- pending|extracted|embedded|ready|failed
  ingest_error  text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz,
  unique (tenant_id, collection_id, checksum)
);
create index if not exists ix_docs_status on docs.documents (ingest_status);
create index if not exists ix_docs_meta   on docs.documents using gin (metadata jsonb_path_ops);
create index if not exists ix_docs_tsv    on docs.documents using gin (content_tsv);

drop trigger if exists trg_docs_touch on docs.documents;
create trigger trg_docs_touch before update on docs.documents
  for each row execute function lakebase_meta.touch_updated_at();

create table if not exists docs.document_chunks (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null default '00000000-0000-0000-0000-000000000000',
  document_id uuid not null references docs.documents(id) on delete cascade,
  chunk_index int  not null,
  content_text text not null,
  token_count int,
  embedding   vector(1024),                         -- dim must match collection.embedding_dim
  metadata    jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now(),
  unique (document_id, chunk_index)
);
-- Build HNSW after first bulk load for large corpora.
create index if not exists ix_chunks_embedding
  on docs.document_chunks using hnsw (embedding vector_cosine_ops);
