"""Run the CONVERTED (candidate) PySpark `transform(spark)` on a data sample.

backend="databricks" executes on your workspace via Databricks Connect;
backend="local" executes on local pyspark for dry-run. Same code, same sample,
so the result is directly comparable to the reference run.
"""
from __future__ import annotations

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
    transform = _load_transform(code)
    spark = get_spark(backend)
    register_tables(spark, tables)
    return transform(spark).toPandas()
