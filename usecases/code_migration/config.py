"""Static metadata for the code_migration use case: input schema + example registry."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLES_DIR = HERE / "examples"
CONVERTED_DIR = HERE / "converted"  # converted PySpark written here (becomes PR content)

# Input tables available to every converted transform (registered as temp views).
TABLE_SCHEMA = """\
Available input tables (read via spark.table("<name>")):

  regions(region_id INT, region_name STRING)
  customers(customer_id INT, region_id INT, signup_date DATE)
  orders(order_id INT, customer_id INT, order_date DATE, amount DOUBLE, status STRING)
"""


@dataclass(frozen=True)
class Example:
    key: str            # cli selector
    path: Path          # source file
    expected_language: str  # for reporting; detection is still run live


EXAMPLES: dict[str, Example] = {
    "sql": Example("sql", EXAMPLES_DIR / "sql" / "revenue_by_region.sql", "sql"),
    "dbt": Example("dbt", EXAMPLES_DIR / "dbt" / "customer_ltv.sql", "dbt"),
    "spark": Example("spark", EXAMPLES_DIR / "spark" / "active_users.py", "spark"),
}
