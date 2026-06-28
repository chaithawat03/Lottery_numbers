from __future__ import annotations

from itertools import combinations

import pandas as pd


def _combos(value: str, size: int) -> list[str]:
    return ["-".join(sorted(c)) for c in combinations(list(value), size)]


def _frequency(series: pd.Series, size: int, label: str) -> pd.DataFrame:
    rows: list[str] = []
    for value in series.dropna():
        rows.extend(_combos(str(value), size))
    counts = pd.Series(rows, dtype="object").value_counts()
    df = counts.rename("count").reset_index()
    df.columns = [label, "count"]
    return df


def digit_pair_frequency(series: pd.Series) -> pd.DataFrame:
    return _frequency(series, 2, "pair")


def digit_triple_frequency(series: pd.Series) -> pd.DataFrame:
    return _frequency(series, 3, "triple")
