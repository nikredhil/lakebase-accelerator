"""Deterministic mock data for the code_migration use case.

Small by design (Manas: small data, 1-2 node cluster). Writes parquet to
data/raw/ and a downsampled copy to data/sample/ used for the dual-run check.

Schema (shared by all three examples):
  regions(region_id, region_name)
  customers(customer_id, region_id, signup_date)
  orders(order_id, customer_id, order_date, amount, status)
"""
from __future__ import annotations

import datetime as dt
import random
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
SAMPLE = HERE / "sample"

SEED = 42
N_CUSTOMERS = 200
N_ORDERS = 2000
REGIONS = ["North", "South", "East", "West"]
STATUSES = ["completed", "pending", "cancelled"]


def _build() -> dict[str, pd.DataFrame]:
    rng = random.Random(SEED)

    regions = pd.DataFrame(
        {"region_id": range(1, len(REGIONS) + 1), "region_name": REGIONS}
    )

    base_signup = dt.date(2023, 1, 1)
    customers = pd.DataFrame(
        {
            "customer_id": range(1, N_CUSTOMERS + 1),
            "region_id": [rng.randint(1, len(REGIONS)) for _ in range(N_CUSTOMERS)],
            "signup_date": [
                base_signup + dt.timedelta(days=rng.randint(0, 365))
                for _ in range(N_CUSTOMERS)
            ],
        }
    )

    base_order = dt.date(2024, 1, 1)
    orders = pd.DataFrame(
        {
            "order_id": range(1, N_ORDERS + 1),
            "customer_id": [rng.randint(1, N_CUSTOMERS) for _ in range(N_ORDERS)],
            "order_date": [
                base_order + dt.timedelta(days=rng.randint(0, 364))
                for _ in range(N_ORDERS)
            ],
            "amount": [round(rng.uniform(5, 500), 2) for _ in range(N_ORDERS)],
            "status": [rng.choices(STATUSES, weights=[0.7, 0.2, 0.1])[0] for _ in range(N_ORDERS)],
        }
    )
    return {"regions": regions, "customers": customers, "orders": orders}


def generate(sample_frac: float = 0.25) -> dict[str, Path]:
    """Write full + sampled parquet. Returns the sample-dir table->path map."""
    RAW.mkdir(parents=True, exist_ok=True)
    SAMPLE.mkdir(parents=True, exist_ok=True)
    tables = _build()
    paths: dict[str, Path] = {}
    for name, df in tables.items():
        df.to_parquet(RAW / f"{name}.parquet", index=False)
        # Sample orders (the big table); keep dimensions whole for referential integrity.
        sdf = df.sample(frac=sample_frac, random_state=SEED) if name == "orders" else df
        sample_path = SAMPLE / f"{name}.parquet"
        sdf.to_parquet(sample_path, index=False)
        paths[name] = sample_path
    return paths


def load_sample() -> dict[str, pd.DataFrame]:
    """Read the sample tables as pandas DataFrames (generates them if missing)."""
    if not (SAMPLE / "orders.parquet").exists():
        generate()
    return {p.stem: pd.read_parquet(p) for p in SAMPLE.glob("*.parquet")}


if __name__ == "__main__":
    out = generate()
    print("Sample tables written:")
    for name, path in out.items():
        print(f"  {name:10s} -> {path.relative_to(HERE.parent)}")
