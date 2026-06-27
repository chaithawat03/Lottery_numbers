from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


def shannon_entropy(counts: pd.Series) -> float:
    total = counts.sum()
    if total == 0:
        return 0.0
    p = counts[counts > 0] / total
    return float(-(p * np.log2(p)).sum())


def chi_square_uniform(counts: pd.Series, categories: int) -> tuple[float, float]:
    observed = counts.to_numpy(dtype=float)
    if len(observed) > categories:
        raise ValueError(
            f"counts has {len(observed)} values but categories={categories}"
        )
    if len(observed) < categories:
        observed = np.concatenate([observed, np.zeros(categories - len(observed))])
    expected = np.full(categories, observed.sum() / categories)
    stat, p = scipy_stats.chisquare(observed, expected)
    return float(stat), float(p)


def describe_numeric(series: pd.Series) -> dict[str, float]:
    """Population descriptive statistics (mean/median/mode/variance/std).

    variance and std use ddof=0 (population) because the dataset is the full
    population of historical draws, not a sample.
    """
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return {k: float("nan") for k in ("mean", "median", "mode", "variance", "std")}
    return {
        "mean": float(s.mean()),
        "median": float(s.median()),
        "mode": float(s.mode().iloc[0]),
        "variance": float(s.var(ddof=0)),
        "std": float(s.std(ddof=0)),
    }


def correlation_matrix(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    numeric = df[columns].apply(pd.to_numeric, errors="coerce")
    return numeric.corr(method="pearson")
