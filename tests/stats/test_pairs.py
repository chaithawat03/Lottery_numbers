import pandas as pd

from lottery.stats.pairs import digit_pair_frequency, digit_triple_frequency


def test_digit_pair_frequency():
    f = digit_pair_frequency(pd.Series(["12", "21"]))
    assert f.iloc[0]["pair"] == "1-2"
    assert f.iloc[0]["count"] == 2


def test_digit_triple_frequency():
    f = digit_triple_frequency(pd.Series(["123"]))
    assert set(f["triple"]) == {"1-2-3"}
