import pandas as pd

from lottery.stats.sequence import markov_transition, repeating_digit_counts


def test_markov_transition_rows_sum_to_one():
    m = markov_transition(pd.Series(["121"]))
    assert abs(m.loc[1, 2] - 1.0) < 1e-9
    assert abs(m.loc[2, 1] - 1.0) < 1e-9


def test_repeating_digit_counts():
    r = repeating_digit_counts(pd.Series(["112"]))
    assert r[r["max_repeat"] == 2]["count"].iloc[0] == 1
