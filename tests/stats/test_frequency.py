import pandas as pd

from lottery.stats.frequency import current_gap, frequency, hot_cold


def test_frequency_counts_and_probability():
    f = frequency(pd.Series(["01", "01", "02", "03"]))
    top = f.iloc[0]
    assert top["value"] == "01"
    assert top["count"] == 2
    assert abs(top["probability"] - 0.5) < 1e-9


def test_hot_cold_split():
    hot, cold = hot_cold(pd.Series(["01", "01", "01", "02", "03"]), top_n=1)
    assert hot.iloc[0]["value"] == "01"
    assert cold.iloc[0]["count"] == 1


def test_current_gap():
    g = current_gap(pd.Series(["01", "02", "03", "02"]))
    assert g[g["value"] == "02"]["gap"].iloc[0] == 0
    assert g[g["value"] == "01"]["gap"].iloc[0] == 3


def test_current_gap_empty_series():
    g = current_gap(pd.Series([], dtype="string"))
    assert list(g.columns) == ["value", "gap"]
    assert len(g) == 0
