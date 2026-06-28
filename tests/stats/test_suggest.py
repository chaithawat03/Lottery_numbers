import pandas as pd

from lottery.stats.suggest import (
    CATEGORIES,
    DISCLAIMER,
    firstprize_digit_frequency,
    score_candidates,
    suggest_all,
    suggest_category,
)

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

ALL_COLS = [
    "DrawDate", "Year", "Month", "FirstPrize", "Last2",
    "Front3_1", "Front3_2", "Back3_1", "Back3_2", "Back3_3", "Back3_4",
]


def _sample_df():
    return pd.DataFrame(
        [
            ["2569-06-01", 2569, 6, "111222", "22", pd.NA, pd.NA, "777", "888", pd.NA, pd.NA],
            ["2569-06-16", 2569, 6, "111333", "33", "434", "758", "777", "999", pd.NA, pd.NA],
        ],
        columns=ALL_COLS,
    )


def test_suggest_category_back3_combines_columns():
    out = suggest_category(_sample_df(), "back3", top_n=5)
    # "777" appears in Back3_1 of both rows -> highest count
    assert out.iloc[0]["value"] == "777"


def test_suggest_category_top_n_limits_rows():
    out = suggest_category(_sample_df(), "last2", top_n=1)
    assert len(out) == 1


def test_firstprize_digit_frequency_shape():
    out = firstprize_digit_frequency(_sample_df())
    assert list(out.columns) == ["position", "digit", "count"]
    # position 1 is "1" in both six-digit prizes
    pos1 = out[(out["position"] == 1) & (out["digit"] == "1")]
    assert pos1.iloc[0]["count"] == 2


def test_suggest_all_has_every_category():
    out = suggest_all(_sample_df(), top_n=3)
    for cat in CATEGORIES:
        assert cat in out
    assert "firstprize_digits" in out
