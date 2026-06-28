import pytest

from lottery.data.myhora import DrawResult, fetch_draws, parse_rows, validate

MODERN_BLOCK = (
    "<div class='rowx div-link' onclick=\"result-16-06-2569.aspx\">"
    "<div class='row-hld'>287184</div>"
    "<div class='row-hld'>84</div>"
    "<div class='row-hld'>184</div>"
    "<div class='row-hld'>48</div>"
    "<div class='row-hld'><u>434</u> <u>758</u> 007 721</div>"
    "</div>"
)

OLD_BLOCK = (
    "<div class='rowx div-link' onclick=\"result-16-12-2533.aspx\">"
    "<div class='row-hld'>4407799</div>"
    "<div class='row-hld'>99</div>"
    "<div class='row-hld'>799</div>"
    "<div class='row-hld'>21</div>"
    "<div class='row-hld'>708 359 171 238</div>"
    "</div>"
)


def test_parse_rows_modern_format():
    rows = parse_rows(MODERN_BLOCK)
    assert len(rows) == 1
    d = rows[0]
    assert d.DrawDate == "2569-06-16"
    assert d.FirstPrize == "287184"
    assert d.Last2 == "48"
    assert (d.Front3_1, d.Front3_2) == ("434", "758")
    assert (d.Back3_1, d.Back3_2) == ("007", "721")


def test_parse_rows_old_format_four_backs_no_fronts():
    d = parse_rows(OLD_BLOCK)[0]
    assert d.FirstPrize == "4407799"
    assert (d.Front3_1, d.Front3_2) == ("", "")
    assert (d.Back3_1, d.Back3_2, d.Back3_3, d.Back3_4) == ("708", "359", "171", "238")


def test_validate_rejects_empty():
    with pytest.raises(ValueError):
        validate([])


def test_fetch_draws_uses_injected_html(monkeypatch):
    html = MODERN_BLOCK + OLD_BLOCK
    monkeypatch.setattr("lottery.data.myhora.fetch_html", lambda url=None: html)
    monkeypatch.setattr("lottery.data.myhora.validate", lambda results: None)
    rows = fetch_draws()
    assert [r.DrawDate for r in rows] == ["2533-12-16", "2569-06-16"]  # sorted
    assert isinstance(rows[0], DrawResult)
