import pytest

from lottery.data.myhora import DrawResult
from lottery.data.repository import DrawRepository
from lottery.data.updater import UpdateError, update_dataset


def _draw(date: str) -> DrawResult:
    return DrawResult(
        DrawDate=date, Year=int(date[:4]), Month=int(date[5:7]),
        FirstPrize="123456", Last2="00",
        Front3_1="", Front3_2="", Back3_1="000", Back3_2="111",
        Back3_3="", Back3_4="",
    )


def test_update_from_empty_then_incremental(tmp_path):
    repo = DrawRepository(tmp_path / "t.sqlite", tmp_path / "t.csv")

    r1 = update_dataset(repo, source=lambda: [_draw("2569-06-01"), _draw("2569-06-16")])
    assert r1.added == 2
    assert r1.latest_before is None
    assert r1.latest_after == "2569-06-16"

    r2 = update_dataset(
        repo,
        source=lambda: [_draw("2569-06-01"), _draw("2569-06-16"), _draw("2569-07-01")],
    )
    assert r2.added == 1
    assert r2.new_dates == ["2569-07-01"]
    assert r2.latest_before == "2569-06-16"
    assert r2.latest_after == "2569-07-01"
    assert len(repo.load()) == 3


def test_update_idempotent_when_no_new(tmp_path):
    repo = DrawRepository(tmp_path / "t.sqlite", tmp_path / "t.csv")
    update_dataset(repo, source=lambda: [_draw("2569-07-01")])
    r = update_dataset(repo, source=lambda: [_draw("2569-07-01")])
    assert r.added == 0
    assert r.new_dates == []
    assert len(repo.load()) == 1


def test_update_wraps_source_errors(tmp_path):
    repo = DrawRepository(tmp_path / "t.sqlite", tmp_path / "t.csv")

    def boom() -> list[DrawResult]:
        raise OSError("network down")

    with pytest.raises(UpdateError):
        update_dataset(repo, source=boom)
