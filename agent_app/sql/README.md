# Vendored schema modules

These are **deploy-safe copies** of the canonical migrations under
`/migrations` (`meta/000_prelude.sql`, `meta/001_ledger.sql`,
`core/001_core.sql`, `agent/001_agent.sql`). The Databricks App container only
ships `./app`, so the app vendors the SQL it applies here. They are loaded in
filename order (`00_…`, `01_…`, …) by `app/blueprints.py::load_sql_modules()`
and run against a Lakebase instance by `app/db.py::apply_schema()`.

Keep in sync with `/migrations` when those change.
