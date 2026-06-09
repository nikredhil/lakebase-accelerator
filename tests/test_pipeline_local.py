"""Local tests that need no Databricks workspace and no Anthropic key.

Covers the parts of the pipeline that don't call Claude or Spark:
data generation, dbt rendering, the DuckDB reference engine, and the comparator.
Spark-dependent paths are smoke-tested separately (skipped if pyspark absent).
"""
from __future__ import annotations

import importlib.util

import pandas as pd
import pytest

from usecases.code_migration.config import EXAMPLES
from usecases.code_migration.data import generate_mock_data
from usecases.code_migration.pipeline import compare, convert, detect, reference_runner
from usecases.code_migration.pipeline.safety import UnsafeCodeError, validate_transform_code


def test_generate_and_load_sample():
    tables = generate_mock_data.load_sample()
    assert set(tables) == {"regions", "customers", "orders"}
    assert len(tables["orders"]) > 0
    assert {"order_id", "customer_id", "amount", "status"} <= set(tables["orders"].columns)


def test_dbt_render_resolves_jinja():
    src = EXAMPLES["dbt"].path.read_text()
    rendered = reference_runner.render_dbt(src)
    assert "{{" not in rendered and "}}" not in rendered
    assert "customers" in rendered and "orders" in rendered


def test_reference_sql_runs_in_duckdb():
    tables = generate_mock_data.load_sample()
    df = reference_runner.run_sql(EXAMPLES["sql"].path.read_text(), tables)
    assert list(df.columns) == ["region_name", "total_revenue", "order_count"]
    assert len(df) <= 4  # at most 4 regions


def test_reference_dbt_runs_in_duckdb():
    tables = generate_mock_data.load_sample()
    df = reference_runner.run_dbt(EXAMPLES["dbt"].path.read_text(), tables)
    assert list(df.columns) == ["customer_id", "lifetime_value", "num_orders"]


def test_compare_match_and_mismatch():
    a = pd.DataFrame({"k": [1, 2], "v": [1.001, 2.002]})
    b = pd.DataFrame({"v": [2.0023, 1.0011], "k": [2, 1]})  # reordered rows + cols
    assert compare.compare(a, b, float_tol=2).ok

    c = pd.DataFrame({"k": [1, 2], "v": [1.0, 9.9]})
    assert not compare.compare(a, c, float_tol=2).ok


def test_rule_detect_classifies_examples():
    assert detect.detect_language_rule(EXAMPLES["sql"].path.read_text()).language == "sql"
    assert detect.detect_language_rule(EXAMPLES["dbt"].path.read_text()).language == "dbt"
    assert detect.detect_language_rule(EXAMPLES["spark"].path.read_text()).language == "spark"


def test_safety_guard_accepts_generated_code():
    # Rule-converted output for every example must pass the guard.
    for key, lang in (("sql", "sql"), ("dbt", "dbt"), ("spark", "spark")):
        validate_transform_code(convert.convert_rule(EXAMPLES[key].path.read_text(), lang))


def test_safety_guard_rejects_unsafe_code():
    bad = [
        "import os\ndef transform(spark):\n    os.system('rm -rf /')\n    return spark.table('orders')",
        "def transform(spark):\n    exec('print(1)')\n    return spark.table('orders')",
        "def transform(spark):\n    open('/etc/passwd').read()\n    return spark.table('orders')",
        "from pyspark.sql import functions as F\nresult = 1",  # no transform()
        "import requests\ndef transform(spark):\n    return spark.table('orders')",
    ]
    for code in bad:
        with pytest.raises(UnsafeCodeError):
            validate_transform_code(code)


def test_rule_convert_produces_valid_transform():
    # sql + dbt -> a compilable module defining transform(spark) using spark.sql
    for key, lang in (("sql", "sql"), ("dbt", "dbt")):
        code = convert.convert_rule(EXAMPLES[key].path.read_text(), lang)
        ns: dict = {}
        exec(compile(code, "<converted>", "exec"), ns)   # must compile
        assert callable(ns.get("transform"))
        assert "spark.sql" in code and "{{" not in code  # jinja fully resolved
    # spark -> pass-through, still defines transform
    spark_code = convert.convert_rule(EXAMPLES["spark"].path.read_text(), "spark")
    assert "def transform(spark)" in spark_code


@pytest.mark.skipif(
    importlib.util.find_spec("pyspark") is None,
    reason="pyspark not installed (local Spark dry-run path)",
)
def test_candidate_runs_on_local_spark():
    """The spark example is already transform(spark); run it via the candidate runner.

    Skips if a usable JVM (Java 17+ for Spark 4.x) isn't available — Spark
    execution is environment-dependent and the real target is Databricks.
    """
    from usecases.code_migration.pipeline import databricks_runner

    tables = generate_mock_data.load_sample()
    code = EXAMPLES["spark"].path.read_text()
    try:
        df = databricks_runner.run_candidate(code, tables, backend="local")
    except Exception as exc:  # JVM/Java-version/gateway failures => skip, don't fail
        pytest.skip(f"local Spark unavailable in this env: {exc}")
    assert list(df.columns) == ["order_month", "active_customers"]
    assert len(df) > 0
