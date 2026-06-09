"""Run converted SQL on a Databricks **serverless SQL warehouse** (fast: ~10s resume).

The converted PySpark is `spark.sql(<SQL>)`; for validation we run that SQL on the
warehouse via the Statement Execution API. The sample tables are embedded as CTEs
so the statement is self-contained — no table creation/cleanup, works instantly on
serverless. Returns a typed pandas DataFrame to compare against the DuckDB reference.
"""
from __future__ import annotations

import datetime as dt
import time

import pandas as pd


def _lit(val, is_date: bool) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "NULL"
    if is_date:
        if isinstance(val, (dt.date, dt.datetime, pd.Timestamp)):
            val = pd.Timestamp(val).date().isoformat()
        return f"DATE '{val}'"
    if isinstance(val, (int,)) and not isinstance(val, bool):
        return str(val)
    if isinstance(val, float):
        return repr(val)
    s = str(val).replace("'", "''")
    return f"'{s}'"


def _cte(name: str, df: pd.DataFrame) -> str:
    cols = list(df.columns)
    date_cols = {c for c in cols if c.endswith("_date")}
    rows = []
    for _, r in df.iterrows():
        vals = ", ".join(_lit(r[c], c in date_cols) for c in cols)
        rows.append(f"({vals})")
    collist = ", ".join(cols)
    values = ",\n    ".join(rows)
    return f"{name} AS (SELECT * FROM (VALUES\n    {values}\n) AS _t({collist}))"


def _cast(series: pd.Series, type_name: str) -> pd.Series:
    t = (type_name or "").upper()
    if t in ("DOUBLE", "FLOAT", "DECIMAL"):
        return pd.to_numeric(series, errors="coerce").astype(float)
    if t in ("LONG", "INT", "INTEGER", "BIGINT", "SHORT", "BYTE"):
        return pd.to_numeric(series, errors="coerce").astype("int64")
    return series.astype(str)


def run_candidate_sql(inner_sql: str, tables: dict[str, pd.DataFrame], warehouse_id: str, w=None) -> pd.DataFrame:
    from databricks.sdk import WorkspaceClient

    w = w or WorkspaceClient()
    ctes = ",\n".join(_cte(n, df) for n, df in tables.items())
    statement = f"WITH {ctes}\n{inner_sql}"

    resp = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id, statement=statement, wait_timeout="50s"
    )
    # Poll if the warehouse was still resuming.
    deadline = time.time() + 180
    while resp.status and resp.status.state and resp.status.state.value in ("PENDING", "RUNNING"):
        if time.time() > deadline:
            raise RuntimeError("SQL statement timed out.")
        time.sleep(3)
        resp = w.statement_execution.get_statement(resp.statement_id)

    state = resp.status.state.value if resp.status and resp.status.state else "?"
    if state != "SUCCEEDED":
        err = resp.status.error.message if (resp.status and resp.status.error) else "unknown"
        raise RuntimeError(f"SQL statement {state}: {err}")

    cols = [c.name for c in resp.manifest.schema.columns]
    types = [c.type_name.value if hasattr(c.type_name, "value") else str(c.type_name)
             for c in resp.manifest.schema.columns]
    data = (resp.result.data_array or []) if resp.result else []
    df = pd.DataFrame(data, columns=cols)
    for c, t in zip(cols, types):
        df[c] = _cast(df[c], t)
    return df
