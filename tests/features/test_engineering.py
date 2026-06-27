import pandas as pd

from lottery.features.engineering import add_features


def test_add_features_first_prize():
    df = pd.DataFrame({"FirstPrize": pd.array(["123456"], dtype="string"),
                       "Last2": pd.array(["07"], dtype="string")})
    out = add_features(df)
    assert out["fp_digit_sum"].iloc[0] == 21
    assert out["fp_odd_count"].iloc[0] == 3
    assert out["fp_even_count"].iloc[0] == 3
    assert out["fp_high_count"].iloc[0] == 2
    assert out["fp_low_count"].iloc[0] == 4
    assert out["last2_int"].iloc[0] == 7


def test_add_features_handles_na_prize():
    df = pd.DataFrame({"FirstPrize": pd.array([pd.NA], dtype="string"),
                       "Last2": pd.array(["10"], dtype="string")})
    out = add_features(df)
    assert pd.isna(out["fp_digit_sum"].iloc[0])
    assert out["last2_int"].iloc[0] == 10
