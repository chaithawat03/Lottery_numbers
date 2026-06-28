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
