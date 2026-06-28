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


def test_back3_recency_uses_chronological_order():
    """Regression guard: old pd.concat column-stacking placed pre-2015-era
    Back3_3/Back3_4 at the END of the series, falsely making them appear most
    recent (lowest gap => highest recency_score).  Row-major reshape (.values.ravel)
    puts the newest draw's values at the end so current_gap and tail() reflect
    actual chronological recency.  This test FAILS on the column-stacked bug."""
    df = pd.DataFrame(
        [
            # Old draw (sorted first): Back3_3/Back3_4 non-null (pre-2015 era).
            ["2533-01-01", 2533, 1, "1234567", "11", pd.NA, pd.NA, "100", "200", "300", "400"],
            # New draw (sorted last): Back3_3/Back3_4 null (modern era).
            ["2569-06-16", 2569, 6, "111222", "22", "434", "758", "500", "601", pd.NA, pd.NA],
        ],
        columns=ALL_COLS,
    )
    # Pure recency weight: only distance from end of the series matters.
    out = suggest_category(
        df, "back3", weights={"frequency": 0, "recency": 1, "trend": 0}
    )
    values_in_order = out["value"].tolist()
    # "601" (Back3_2 of the newest draw) must rank above "300" and "400"
    # (Back3_3/Back3_4 of the OLD draw).  With the column-stacking bug "300"
    # lands at index 4 and "400" at index 6 in the series, giving them gap 3
    # and 1 respectively — both smaller than "601"'s gap of 4 — so the bug
    # makes them appear falsely more recent.
    assert values_in_order.index("601") < values_in_order.index("300"), (
        "601 (newest draw Back3_2) must have higher recency_score than 300 (old Back3_3); "
        "column-stacking bug present if this fails"
    )
    assert values_in_order.index("601") < values_in_order.index("400"), (
        "601 (newest draw Back3_2) must have higher recency_score than 400 (old Back3_4); "
        "column-stacking bug present if this fails"
    )


def test_firstprize_digit_frequency_excludes_7_digit_prizes():
    """7-digit FirstPrize rows (pre-2015 era characteristic) must be excluded
    from firstprize_digit_frequency, which is defined for 6-digit prizes only."""
    df = pd.DataFrame(
        [
            # 7-digit prize (pre-2015 era) — must be excluded.
            ["2533-01-01", 2533, 1, "4407799", "21", pd.NA, pd.NA, "708", "359", "171", "238"],
            # 6-digit prize (modern era) — must be counted.
            ["2569-06-16", 2569, 6, "287184", "48", "434", "758", "007", "721", pd.NA, pd.NA],
        ],
        columns=ALL_COLS,
    )
    out = firstprize_digit_frequency(df)
    # Only "287184" contributes; "4407799" is excluded by the str.len() == 6 filter.
    # Position 1 of "287184" is "2" with count=1; "4" (from the 7-digit prize) absent.
    pos1 = out[out["position"] == 1]
    assert set(pos1["digit"].tolist()) == {"2"}, (
        "7-digit prizes must be excluded; unexpected digits at position 1"
    )
    assert pos1.iloc[0]["count"] == 1
