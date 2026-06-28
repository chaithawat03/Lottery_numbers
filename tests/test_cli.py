import pytest

from lottery.cli import main


def test_suggest_command_prints_disclaimer(capsys):
    rc = main(["suggest"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "prediction" in out.lower()
    assert "last2" in out


def test_unknown_command_errors():
    with pytest.raises(SystemExit):
        main(["bogus"])
