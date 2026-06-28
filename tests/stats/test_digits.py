import pandas as pd

from lottery.stats.digits import (
    high_low_ratio,
    is_ascending,
    is_descending,
    mirror_value,
    odd_even_ratio,
    position_distribution,
)


def test_position_distribution():
    d = position_distribution(pd.Series(["12", "13"]))
    assert d.loc[1, "pos_0"] == 2
    assert d.loc[2, "pos_1"] == 1


def test_odd_even_ratio():
    r = odd_even_ratio(pd.Series(["13"]))
    assert r[r["kind"] == "odd"]["count"].iloc[0] == 2
    assert r[r["kind"] == "even"]["count"].iloc[0] == 0


def test_high_low_ratio():
    r = high_low_ratio(pd.Series(["59"]))
    assert r[r["kind"] == "high"]["count"].iloc[0] == 2


def test_mirror_value():
    assert mirror_value("012") == "567"


def test_running_numbers():
    assert is_ascending("123") is True
    assert is_descending("321") is True
    assert is_ascending("122") is False
