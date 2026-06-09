"""Step 4: compare reference vs candidate results — they must match."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class CompareResult:
    ok: bool
    detail: str


def _normalize(df: pd.DataFrame, float_tol: int) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c) for c in df.columns]
    df = df[sorted(df.columns)]                       # column order independent
    for c in df.select_dtypes(include="float").columns:
        df[c] = df[c].round(float_tol)
    df = df.sort_values(by=list(df.columns)).reset_index(drop=True)  # row order independent
    return df


def compare(reference: pd.DataFrame, candidate: pd.DataFrame, float_tol: int = 2) -> CompareResult:
    ref = _normalize(reference, float_tol)
    cand = _normalize(candidate, float_tol)

    if list(ref.columns) != list(cand.columns):
        return CompareResult(False, f"Column mismatch: reference={list(ref.columns)} candidate={list(cand.columns)}")
    if ref.shape != cand.shape:
        return CompareResult(False, f"Shape mismatch: reference={ref.shape} candidate={cand.shape}")

    # Tolerant compare: floats within one cent (cross-engine rounding differs:
    # DuckDB uses banker's rounding, Spark uses half-up), other columns exact.
    atol = 10.0 ** (-float_tol) + 1e-9
    diff_mask = pd.Series(False, index=ref.index)
    for c in ref.columns:
        if ref[c].dtype.kind in "fc":
            close = np.isclose(ref[c].to_numpy(dtype=float), cand[c].to_numpy(dtype=float),
                               atol=atol, rtol=0, equal_nan=True)
            diff_mask |= ~close
        else:
            diff_mask |= (ref[c].to_numpy() != cand[c].to_numpy())

    if not diff_mask.any():
        return CompareResult(True, f"Match: {ref.shape[0]} rows x {ref.shape[1]} cols (within {atol:.3g}).")
    sample = pd.concat(
        [ref[diff_mask].head(5).add_prefix("ref_"), cand[diff_mask].head(5).add_prefix("cand_")],
        axis=1,
    )
    return CompareResult(False, f"{int(diff_mask.sum())} differing rows. Sample:\n{sample.to_string(index=False)}")
