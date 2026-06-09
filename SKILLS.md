# SKILLS.md — accumulated conversion heuristics

This file is the agent's long-term memory for converting SQL / Spark / dbt code
into Databricks PySpark. It is **injected into the conversion prompt** and
**appended to automatically** whenever a conversion fails validation and the
agent extracts a reusable lesson (Karpathy-style "the AI is learning").

Keeping lessons here instead of re-deriving them every run is what saves tokens:
the model reads a compact list of known gotchas rather than rediscovering them.

Rules for entries: one bullet per lesson, imperative, specific, deduplicated.
Newest lessons go at the bottom of the relevant section.

---

## Contract (every conversion MUST follow)

- Output a single Python module defining `def transform(spark):` that returns a
  Spark `DataFrame`. No `spark.stop()`, no `.show()`, no `print`, no file writes.
- Read every input table via `spark.table("<name>")` — never hardcode paths.
  The harness pre-registers the input tables as temp views before calling you.
- Do not create the SparkSession; use the `spark` passed in.
- Preserve output column names, types, and intended row semantics exactly.
- Return the DataFrame; the harness handles `.collect()` / comparison.

## SQL → PySpark

- `ROUND(x, n)` → `F.round(F.col("x"), n)`; keep the same precision or row counts
  diverge after float aggregation.
- `COUNT(*)` → `F.count(F.lit(1))`; `COUNT(DISTINCT x)` → `F.countDistinct("x")`.
- SQL `JOIN ... ON a = b` → `.join(other, on=..., how="inner")`; default join is inner.
- Keep `ORDER BY` as a final `.orderBy(...)` so ordered comparisons match.
- A faithful, low-risk path for plain SQL is `spark.sql(<the original query>)` after
  the temp views exist — prefer it when the SQL has no engine-specific functions.

## dbt → PySpark

- Strip `{{ config(...) }}` — it is build metadata, not logic.
- `{{ ref('model_name') }}` → `spark.table("model_name")` (the upstream table name).
- `{{ source('src', 'table') }}` → `spark.table("table")` (use the table, ignore the source alias).
- dbt models are `SELECT`s; the materialization (table/view/incremental) is the
  harness's concern, not the transform's.

## Spark → Databricks PySpark

- Spark code is usually near-identity; main job is enforcing the `transform(spark)`
  contract and removing `SparkSession.builder...getOrCreate()` / I/O side effects.
- Replace `spark.read.parquet("/path")` / `spark.read.table(...)` with `spark.table("<name>")`.

## Learned lessons (auto-appended on validation failure)

<!-- LESSONS-START -->
<!-- LESSONS-END -->
