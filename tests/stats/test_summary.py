import pandas as pd

from lottery.stats.summary import chi_square_uniform, describe_numeric, shannon_entropy


def test_shannon_entropy_uniform():
    assert shannon_entropy(pd.Series([1, 1, 1, 1])) == 2.0


def test_chi_square_uniform_perfect_fit():
    stat, p = chi_square_uniform(pd.Series([10, 10, 10, 10]), 4)
    assert stat == 0.0
    assert round(p, 6) == 1.0


def test_describe_numeric():
    d = describe_numeric(pd.Series([1, 2, 2, 3]))
    assert d["mean"] == 2.0
    assert d["mode"] == 2.0
    assert d["median"] == 2.0
    assert d["variance"] == 0.5
    assert round(d["std"], 6) == 0.707107


def test_correlation_matrix():
    from lottery.stats.summary import correlation_matrix

    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 4, 6, 8], "c": [4, 3, 2, 1]})
    corr = correlation_matrix(df, ["a", "b", "c"])
    assert round(corr.loc["a", "b"], 6) == 1.0
    assert round(corr.loc["a", "c"], 6) == -1.0
