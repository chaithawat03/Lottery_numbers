"""Experimental, descriptive number scoring.

THESE ARE NOT PREDICTIONS. The lottery is a near-uniform random draw; past
results cannot predict future ones. Scores rank candidates by historical
signals only and exist for educational/descriptive purposes.
"""

from __future__ import annotations

import pandas as pd

from lottery.stats.frequency import current_gap, frequency

DISCLAIMER = (
    "ℹ️ ตัวเลขเหล่านี้เป็นคะแนนจากสถิติย้อนหลังเพื่อการศึกษาเท่านั้น ไม่ใช่การทำนาย "
    "หวยเป็นการสุ่ม ผลในอดีตไม่สามารถทำนายผลในอนาคตได้ "
    "(Experimental scores from historical statistics only — not a prediction. "
    "The lottery is random; past results cannot predict the future.)"
)

DEFAULT_WEIGHTS = {"frequency": 0.5, "recency": 0.25, "trend": 0.25}

_SCORE_COLUMNS = ["value", "freq_score", "recency_score", "trend_score", "score"]


def _normalize(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    if hi == lo:
        return pd.Series(0.0, index=s.index)
    return (s - lo) / (hi - lo)


def score_candidates(
    series: pd.Series,
    *,
    weights: dict[str, float] | None = None,
    recent_window: int = 50,
) -> pd.DataFrame:
    """Score each distinct value by blended frequency/recency/trend signals."""
    weights = weights or DEFAULT_WEIGHTS
    s = series.dropna()
    if s.empty:
        return pd.DataFrame(columns=_SCORE_COLUMNS)

    freq = frequency(s)[["value", "count"]]
    gap = current_gap(s)  # columns: value, gap
    recent_counts = s.tail(recent_window).value_counts()

    df = freq.merge(gap, on="value", how="left")
    df["gap"] = df["gap"].fillna(df["gap"].max())
    df["trend"] = df["value"].map(recent_counts).fillna(0)

    df["freq_score"] = _normalize(df["count"])
    df["recency_score"] = _normalize(df["gap"].max() - df["gap"])
    df["trend_score"] = _normalize(df["trend"])
    df["score"] = (
        weights["frequency"] * df["freq_score"]
        + weights["recency"] * df["recency_score"]
        + weights["trend"] * df["trend_score"]
    )
    return (
        df.sort_values("score", ascending=False)
        .reset_index(drop=True)[_SCORE_COLUMNS]
    )


_BACK3_COLS = ["Back3_1", "Back3_2", "Back3_3", "Back3_4"]
_FRONT3_COLS = ["Front3_1", "Front3_2"]

CATEGORIES = ["last2", "back3", "front3", "firstprize_last3"]


def _category_series(df: pd.DataFrame, category: str) -> pd.Series:
    if category == "last2":
        return df["Last2"]
    if category == "back3":
        # Row-major reshape: each draw's Back3 values are adjacent, draws in
        # ascending DrawDate order so the END of the series = most recent draw.
        # Old pd.concat column-stacking put Back3_3/Back3_4 (pre-2015-only
        # columns) at the end, falsely boosting their recency_score / gap.
        # .values is a 2-D numpy array; ravel("C") = C-order = row-major.
        return pd.Series(df[_BACK3_COLS].values.ravel("C"))
    if category == "front3":
        # Same row-major reshape so the newest draw's Front3 values end the series.
        return pd.Series(df[_FRONT3_COLS].values.ravel("C"))
    if category == "firstprize_last3":
        # Takes last 3 chars of ANY prize length (6- or 7-digit) — era-agnostic.
        # Contrast: firstprize_digit_frequency is 6-digit-only (positional table).
        return df["FirstPrize"].dropna().astype("string").str[-3:]
    raise ValueError(f"Unknown category: {category}")


def suggest_category(
    df: pd.DataFrame,
    category: str,
    *,
    weights: dict[str, float] | None = None,
    recent_window: int = 50,
    top_n: int = 10,
) -> pd.DataFrame:
    series = _category_series(df, category)
    scored = score_candidates(series, weights=weights, recent_window=recent_window)
    return scored.head(top_n).reset_index(drop=True)


def firstprize_digit_frequency(df: pd.DataFrame) -> pd.DataFrame:
    fp = df["FirstPrize"].dropna().astype("string")
    fp = fp[fp.str.len() == 6]
    rows = []
    for pos in range(6):
        counts = fp.str[pos].value_counts()
        for digit, count in counts.items():
            rows.append({"position": pos + 1, "digit": digit, "count": int(count)})
    return (
        pd.DataFrame(rows, columns=["position", "digit", "count"])
        .sort_values(["position", "digit"])
        .reset_index(drop=True)
    )


def suggest_all(
    df: pd.DataFrame,
    *,
    weights: dict[str, float] | None = None,
    recent_window: int = 50,
    top_n: int = 10,
) -> dict[str, pd.DataFrame]:
    out = {
        cat: suggest_category(
            df, cat, weights=weights, recent_window=recent_window, top_n=top_n
        )
        for cat in CATEGORIES
    }
    out["firstprize_digits"] = firstprize_digit_frequency(df)
    return out
