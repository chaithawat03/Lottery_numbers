from pathlib import Path

import pandas as pd

from lottery.data.models import ALL_COLUMNS
from lottery.data.models import ALL_COLUMNS as _COLS
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


def _one_row_frame():
    return pd.DataFrame(
        [
            {
                "DrawDate": "2569-06-16", "Year": 2569, "Month": 6,
                "FirstPrize": "287184", "Last2": "48",
                "Front3_1": "434", "Front3_2": "758",
                "Back3_1": "007", "Back3_2": "721",
                "Back3_3": pd.NA, "Back3_4": pd.NA,
            }
        ],
        columns=_COLS,
    )


def test_latest_date_none_when_missing(tmp_path):
    assert DrawRepository(tmp_path / "nope.sqlite").latest_date() is None


def test_save_then_latest_date_and_load_roundtrip(tmp_path):
    db = tmp_path / "t.sqlite"
    csv = tmp_path / "t.csv"
    repo = DrawRepository(db, csv)
    repo.save(_one_row_frame())
    assert repo.latest_date() == "2569-06-16"
    assert csv.exists()
    loaded = repo.load()
    assert loaded.iloc[0]["FirstPrize"] == "287184"
    assert pd.isna(loaded.iloc[0]["Back3_3"])


def test_save_insert_or_replace_is_idempotent(tmp_path):
    db = tmp_path / "t.sqlite"
    repo = DrawRepository(db)
    repo.save(_one_row_frame())
    repo.save(_one_row_frame())
    assert len(repo.load()) == 1
