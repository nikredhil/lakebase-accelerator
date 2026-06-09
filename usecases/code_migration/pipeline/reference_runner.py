"""Run the ORIGINAL code against the sample to produce the reference result.

- sql / dbt  -> DuckDB (no JVM needed). dbt Jinja is rendered to plain SQL first.
- spark      -> local pyspark (same engine the candidate uses for the spark path).

Returns a pandas DataFrame for comparison against the candidate.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import duckdb
import pandas as pd
from jinja2 import Environment

from usecases.code_migration.pipeline.spark_utils import get_spark, register_tables


# --- dbt rendering: resolve ref()/source()/config() to runnable SQL ---
def render_dbt(model_sql: str) -> str:
    env = Environment()
    template = env.from_string(model_sql)
    return template.render(
        ref=lambda name, *a, **k: name,
        source=lambda src, name, *a, **k: name,
        config=lambda *a, **k: "",
    ).strip()


def run_sql(sql: str, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    con = duckdb.connect()
    try:
        for name, pdf in tables.items():
            con.register(name, pdf)
        return con.execute(sql).df()
    finally:
        con.close()


def run_dbt(model_sql: str, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return run_sql(render_dbt(model_sql), tables)


def run_spark_original(path: Path, tables: dict[str, pd.DataFrame], backend: str = "local") -> pd.DataFrame:
    spec = importlib.util.spec_from_file_location("original_spark_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    if not hasattr(module, "transform"):
        raise AttributeError(f"{path} must define transform(spark)")
    spark = get_spark(backend)
    register_tables(spark, tables)
    return module.transform(spark).toPandas()


def run_reference(
    language: str,
    code: str,
    source_path: Path,
    tables: dict[str, pd.DataFrame],
    spark_backend: str = "local",
) -> pd.DataFrame:
    if language == "sql":
        return run_sql(code, tables)
    if language == "dbt":
        return run_dbt(code, tables)
    if language == "spark":
        return run_spark_original(source_path, tables, backend=spark_backend)
    raise ValueError(f"Cannot run reference for language {language!r}")
