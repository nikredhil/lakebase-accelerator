"""Run the CONVERTED (candidate) PySpark `transform(spark)` on a data sample.

backend="databricks" executes on your workspace via Databricks Connect;
backend="local" executes on local pyspark for dry-run. Same code, same sample,
so the result is directly comparable to the reference run.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from usecases.code_migration.pipeline.spark_utils import get_spark, register_tables


def _load_transform(code: str):
    namespace: dict = {}
    exec(compile(code, "<converted_transform>", "exec"), namespace)  # noqa: S102
    fn = namespace.get("transform")
    if not callable(fn):
        raise ValueError("Converted code does not define a callable transform(spark).")
    return fn


def run_candidate(code: str, tables: dict[str, pd.DataFrame], backend: str = "local") -> pd.DataFrame:
    # Static safety gate BEFORE any execution path (local exec, cluster, or SQL).
    from usecases.code_migration.pipeline.safety import validate_transform_code

    validate_transform_code(code)

    if backend == "databricks_sql":
        # Run the converted SQL on a serverless SQL warehouse (fast; no cluster boot).
        from usecases.code_migration.pipeline.databricks_sql_runner import run_candidate_sql

        wid = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
        if not wid:
            raise RuntimeError("DATABRICKS_WAREHOUSE_ID not set.")
        m = re.search(r'spark\.sql\(\s*"""(.*?)"""', code, re.S)
        inner = m.group(1) if m else code
        return run_candidate_sql(inner, tables, wid)

    if backend == "databricks":
        # Run on a workspace cluster via the Command Execution API (no Connect/JVM locally).
        from usecases.code_migration.pipeline.databricks_command_runner import run_candidate_command

        cluster_id = os.environ.get("DATABRICKS_CLUSTER_ID", "")
        if not cluster_id:
            raise RuntimeError("DATABRICKS_CLUSTER_ID not set (terraform output cluster_id).")
        return run_candidate_command(code, tables, cluster_id)

    # local pyspark
    transform = _load_transform(code)
    spark = get_spark(backend)
    register_tables(spark, tables)
    return transform(spark).toPandas()
