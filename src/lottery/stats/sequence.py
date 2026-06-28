from __future__ import annotations

import numpy as np
import pandas as pd


def markov_transition(series: pd.Series) -> pd.DataFrame:
    matrix = np.zeros((10, 10))
    for value in series.dropna():
        text = str(value)
        for i in range(len(text) - 1):
            matrix[int(text[i])][int(text[i + 1])] += 1
    row_sums = matrix.sum(axis=1, keepdims=True)
    probs = np.divide(matrix, row_sums, out=np.zeros_like(matrix), where=row_sums != 0)
    return pd.DataFrame(probs, index=range(10), columns=range(10))


def repeating_digit_counts(series: pd.Series) -> pd.DataFrame:
    rows: list[int] = []
    for value in series.dropna():
        text = str(value)
        rows.append(max((text.count(d) for d in set(text)), default=0))
    counts = pd.Series(rows, dtype="int64").value_counts().sort_index()
    df = counts.rename("count").reset_index()
    df.columns = ["max_repeat", "count"]
    return df
