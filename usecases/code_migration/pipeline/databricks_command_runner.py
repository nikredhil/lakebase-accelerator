"""Run converted PySpark on a Databricks cluster via the Command Execution API.

This avoids Databricks Connect (which pins a specific local Python version): we
ship the small sample tables + the converted transform to the cluster, register
temp views there, run transform(spark), and return the result as JSON. Works
with just `databricks-sdk` on any local Python.
"""
from __future__ import annotations

import json

import pandas as pd

_MARK_START = "RESULT_JSON_START"
_MARK_END = "RESULT_JSON_END"


def _remote_script(code: str, tables: dict[str, pd.DataFrame]) -> str:
    payload = {name: df.to_csv(index=False) for name, df in tables.items()}
    return f'''
import io, json
import pandas as pd
from pyspark.sql import SparkSession
spark = SparkSession.builder.getOrCreate()

_data = {payload!r}
for _name, _csv in _data.items():
    _pdf = pd.read_csv(io.StringIO(_csv))
    for _c in _pdf.columns:
        if _c.endswith("_date"):
            _pdf[_c] = pd.to_datetime(_pdf[_c]).dt.date
    spark.createDataFrame(_pdf).createOrReplaceTempView(_name)

# --- converted transform ---
{code}
# --- run it ---
_res = transform(spark).toPandas()
print("{_MARK_START}")
print(_res.to_json(orient="records"))
print("{_MARK_END}")
'''


def run_candidate_command(code: str, tables: dict[str, pd.DataFrame], cluster_id: str, w=None) -> pd.DataFrame:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.compute import Language

    w = w or WorkspaceClient()
    ctx = w.command_execution.create_and_wait(cluster_id=cluster_id, language=Language.PYTHON)
    try:
        cmd = w.command_execution.execute_and_wait(
            cluster_id=cluster_id,
            context_id=ctx.id,
            language=Language.PYTHON,
            command=_remote_script(code, tables),
        )
    finally:
        w.command_execution.destroy(cluster_id=cluster_id, context_id=ctx.id)

    results = cmd.results
    if results is None or (results.result_type and str(results.result_type.value) == "error"):
        cause = getattr(results, "cause", None) or getattr(results, "summary", None) or "unknown error"
        raise RuntimeError(f"Databricks command failed: {cause}")

    data = results.data or ""
    if _MARK_START not in data or _MARK_END not in data:
        raise RuntimeError(f"Unexpected command output (no result markers):\n{data[:1000]}")
    payload = data.split(_MARK_START, 1)[1].split(_MARK_END, 1)[0].strip()
    return pd.DataFrame(json.loads(payload))
