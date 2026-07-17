# Lakebase Accelerator — schema migrations

Module-based, idempotent SQL applied to a Lakebase (Postgres 16+) instance after
provisioning. See `docs/design-spec.md` §8.2 and §10 for the design.

## Layout

```
migrations/
  meta/   000_prelude.sql  001_ledger.sql      # always applied first
  core/   001_core.sql                          # always applied
  app/    001_app.sql                           # opt-in
  docs/   001_docs.sql                          # opt-in (unstructured / RAG)
  agent/  001_agent.sql                          # opt-in (agent memory + eval — flagship use case)
```

## Conventions

- **Naming:** `NNN_<slug>.sql`, applied in ascending `NNN` order within a module.
- **Idempotent:** every statement uses `IF NOT EXISTS` / `CREATE OR REPLACE` so a
  re-run is a no-op.
- **Ledger:** `lakebase_meta.schema_migrations(module, version, checksum, applied_at)`
  records what ran. The migrator skips applied `(module, version)` pairs; a checksum
  mismatch on an applied version is a hard error (never a silent re-apply).
- **Order:** `meta` → `core` → (`app`, `docs`, `agent` if selected). `meta` and `core` are
  always applied; the use-case manifest's `schema.modules` selects the rest.
- **Auth:** the migrator connects with a short-lived Databricks-identity credential
  (`sslmode=require`), runs each file in a transaction.

## Extensions required

`pgcrypto` (UUIDs) and `vector` (pgvector); `postgis` optional. Availability on the
target workspace is a P0 check — see design-spec §14 R1.
