from __future__ import annotations

import pandas as pd


def frequency(series: pd.Series) -> pd.DataFrame:
    counts = series.dropna().value_counts()
    total = counts.sum()
    df = counts.rename("count").reset_index()
    df.columns = ["value", "count"]
    df["probability"] = df["count"] / total if total else 0.0
    return df.sort_values("count", ascending=False).reset_index(drop=True)


def hot_cold(series: pd.Series, top_n: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    freq = frequency(series)
    hot = freq.head(top_n).reset_index(drop=True)
    cold = freq.sort_values("count").head(top_n).reset_index(drop=True)
    return hot, cold


def current_gap(series: pd.Series) -> pd.DataFrame:
    s = series.reset_index(drop=True)
    n = len(s)
    last_index: dict[object, int] = {}
    for i, value in s.items():
        if pd.notna(value):
            last_index[value] = i
    rows = [{"value": v, "gap": n - 1 - idx} for v, idx in last_index.items()]
    return pd.DataFrame(rows).sort_values("gap", ascending=False).reset_index(drop=True)
