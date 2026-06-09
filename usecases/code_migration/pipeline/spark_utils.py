"""SparkSession helpers shared by the reference and candidate runners.

backend="databricks" -> Databricks Connect (runs on your workspace cluster).
backend="local"      -> local pyspark (dry-run; needs Java + pyspark).

NOTE: databricks-connect and pyspark must NOT be installed in the same venv.
Pick one per environment via CANDIDATE_BACKEND.
"""
from __future__ import annotations

import pandas as pd

_SESSIONS: dict[str, object] = {}


def get_spark(backend: str = "local"):
    if backend in _SESSIONS:
        return _SESSIONS[backend]

    if backend == "databricks":
        from databricks.connect import DatabricksSession

        spark = DatabricksSession.builder.getOrCreate()
    elif backend == "local":
        from pyspark.sql import SparkSession

        spark = (
            SparkSession.builder.master("local[*]")
            .appName("lakebase-code-migration")
            .config("spark.sql.shuffle.partitions", "4")
            .config("spark.ui.enabled", "false")
            .getOrCreate()
        )
        spark.sparkContext.setLogLevel("ERROR")
    else:
        raise ValueError(f"Unknown backend {backend!r} (use 'databricks' or 'local').")

    _SESSIONS[backend] = spark
    return spark


def register_tables(spark, tables: dict[str, pd.DataFrame]) -> None:
    """Register each pandas table as a temp view so transform(spark) can read it."""
    for name, pdf in tables.items():
        spark.createDataFrame(pdf).createOrReplaceTempView(name)
