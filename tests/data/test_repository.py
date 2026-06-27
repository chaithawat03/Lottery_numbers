from pathlib import Path

import pandas as pd

from lottery.data.models import ALL_COLUMNS
from lottery.data.repository import DrawRepository

DB = Path("dataset/lottery_results.sqlite")


def test_repository_loads_full_dataset():
    df = DrawRepository(DB).load()
    assert len(df) == 872
    assert list(df.columns) == ALL_COLUMNS
    assert df.iloc[0]["DrawDate"] == "2533-01-16"
    assert df.iloc[-1]["DrawDate"] == "2569-06-16"


def test_repository_preserves_leading_zero_and_na():
    df = DrawRepository(DB).load()
    row_old = df[df["DrawDate"] == "2533-02-16"].iloc[0]
    assert row_old["Last2"] == "01"
    row_modern = df[df["DrawDate"] == "2569-06-16"].iloc[0]
    assert row_modern["FirstPrize"] == "287184"
    assert pd.isna(row_modern["Back3_3"])


def test_repository_missing_file_raises():
    try:
        DrawRepository(Path("dataset/does_not_exist.sqlite")).load()
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass
