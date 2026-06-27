from __future__ import annotations

import pandas as pd


def _count(value: object, predicate) -> object:
    if pd.isna(value) or value == "":
        return pd.NA
    return sum(1 for d in str(value) if predicate(int(d)))


def _digit_sum(value: object) -> object:
    if pd.isna(value) or value == "":
        return pd.NA
    return sum(int(d) for d in str(value))


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    fp = out["FirstPrize"]
    out["fp_digit_sum"] = fp.map(_digit_sum).astype("Int64")
    out["fp_odd_count"] = fp.map(lambda v: _count(v, lambda d: d % 2 == 1)).astype("Int64")
    out["fp_even_count"] = fp.map(lambda v: _count(v, lambda d: d % 2 == 0)).astype("Int64")
    out["fp_high_count"] = fp.map(lambda v: _count(v, lambda d: d >= 5)).astype("Int64")
    out["fp_low_count"] = fp.map(lambda v: _count(v, lambda d: d < 5)).astype("Int64")
    out["last2_int"] = pd.to_numeric(out["Last2"], errors="coerce").astype("Int64")
    return out
