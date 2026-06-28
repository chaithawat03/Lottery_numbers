"""Stdlib-only fetch + parse for myhora.com lottery statistics.

Kept dependency-free (no pandas/numpy) so the standalone scraper can import it
under the system interpreter.

Page layout (myhora.com/lottery/stats.aspx): each draw is a
``<div class='rowx div-link'>`` block whose onclick attribute encodes the draw
date (``result-DD-MM-YYYY.aspx``).  Inside, ``row-hld`` divs hold FirstPrize
(cell 0) and Last2 (cell 3).  The final cell holds Front3 numbers wrapped in
``<u>`` tags and Back3 numbers as bare three-digit strings.
"""

from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass

STATS_URL = "https://myhora.com/lottery/stats.aspx?mx=09&vx=40"
USER_AGENT = "Mozilla/5.0 (compatible; lottery-research/1.0)"

_ROW_SPLIT = re.compile(r"<div class='rowx div-link'")
_RESULT_LINK = re.compile(r"result-(\d{2})-(\d{2})-(\d{4})\.aspx")
_ROW_HLD_CELL = re.compile(r"row-hld[^>]*>(.*?)</div>", re.S)
_UNDERLINE = re.compile(r"<u>(.*?)</u>", re.S)
_TAG = re.compile(r"<[^>]+>")
_THREE_DIGITS = re.compile(r"\d{3}")


@dataclass(frozen=True)
class DrawResult:
    """One lottery draw, matching the dataset schema (+ Back3_3/Back3_4)."""

    DrawDate: str  # ISO-style date in the Buddhist calendar, e.g. 2569-06-16
    Year: int  # Buddhist Era (BE) year
    Month: int
    FirstPrize: str
    Last2: str
    Front3_1: str
    Front3_2: str
    Back3_1: str
    Back3_2: str
    Back3_3: str
    Back3_4: str


def fetch_html(url: str = STATS_URL) -> str:
    """Download the statistics page."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")


def _clean(fragment: str) -> str:
    return _TAG.sub("", fragment).strip()


def _at(values: list[str], index: int) -> str:
    return values[index] if index < len(values) else ""


def parse_rows(html: str) -> list[DrawResult]:
    """Parse every draw block in the page into DrawResult records."""
    results: list[DrawResult] = []
    for block in _ROW_SPLIT.split(html)[1:]:
        link = _RESULT_LINK.search(block)
        if not link:
            continue
        day, month, be_year = (int(part) for part in link.groups())

        cells = _ROW_HLD_CELL.findall(block)
        if not cells:
            continue

        first_prize = _clean(cells[0])
        last2 = _clean(cells[3]) if len(cells) > 3 else ""

        combo = cells[-1]
        fronts = [_clean(u) for u in _UNDERLINE.findall(combo)]
        fronts = [f for f in fronts if f]
        backs = _THREE_DIGITS.findall(_clean(_UNDERLINE.sub("", combo)))

        results.append(
            DrawResult(
                DrawDate=f"{be_year:04d}-{month:02d}-{day:02d}",
                Year=be_year,
                Month=month,
                FirstPrize=first_prize,
                Last2=last2,
                Front3_1=_at(fronts, 0),
                Front3_2=_at(fronts, 1),
                Back3_1=_at(backs, 0),
                Back3_2=_at(backs, 1),
                Back3_3=_at(backs, 2),
                Back3_4=_at(backs, 3),
            )
        )
    return results


def validate(results: list[DrawResult]) -> None:
    """Assert known reference values so a layout change fails loudly."""
    if not results:
        raise ValueError("No draws parsed - the page layout may have changed.")

    by_date = {r.DrawDate: r for r in results}

    modern = by_date.get("2569-06-16")
    assert modern is not None, "Missing reference draw 16-06-2569"
    assert modern.FirstPrize == "287184", modern
    assert modern.Last2 == "48", modern
    assert (modern.Front3_1, modern.Front3_2) == ("434", "758"), modern
    assert (modern.Back3_1, modern.Back3_2) == ("007", "721"), modern

    old = by_date.get("2533-12-16")
    assert old is not None, "Missing reference draw 16-12-2533"
    assert old.FirstPrize == "4407799", old
    assert old.Last2 == "21", old
    assert (old.Front3_1, old.Front3_2) == ("", ""), old
    assert (old.Back3_1, old.Back3_2, old.Back3_3, old.Back3_4) == (
        "708",
        "359",
        "171",
        "238",
    ), old


def fetch_draws(url: str = STATS_URL) -> list[DrawResult]:
    """Fetch, parse, sort, and validate the full draw history."""
    results = parse_rows(fetch_html(url))
    results.sort(key=lambda r: r.DrawDate)
    validate(results)
    return results
