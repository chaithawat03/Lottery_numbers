import pandas as pd

from lottery.stats.suggest import DISCLAIMER, score_candidates

COLS = ["value", "freq_score", "recency_score", "trend_score", "score"]


def test_disclaimer_mentions_random_and_not_prediction():
    assert "สุ่ม" in DISCLAIMER
    assert "prediction" in DISCLAIMER.lower()


def test_empty_series_returns_empty_frame_with_columns():
    out = score_candidates(pd.Series([], dtype="string"))
    assert list(out.columns) == COLS
    assert out.empty


def test_frequency_weight_orders_by_count():
    s = pd.Series(["01", "01", "01", "02", "03", "03"])
    out = score_candidates(
        s, weights={"frequency": 1.0, "recency": 0.0, "trend": 0.0}, recent_window=10
    )
    assert list(out.columns) == COLS
    assert out.iloc[0]["value"] == "01"
    assert out.iloc[0]["freq_score"] == 1.0


def test_recency_weight_prefers_most_recent():
    s = pd.Series(["01", "02", "02", "03", "02"])  # 02 drawn most recently
    out = score_candidates(
        s, weights={"frequency": 0.0, "recency": 1.0, "trend": 0.0}
    )
    assert out.iloc[0]["value"] == "02"
