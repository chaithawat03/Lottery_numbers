"""Scrape historical Thai Government Lottery results from myhora.com.

Source page (single request returns the full BE 2533-2569 / CE 1990-2026 range):
    https://myhora.com/lottery/stats.aspx?mx=09&vx=40

    mx=09  -> "show every draw" statistics view
    vx=40  -> number of years to look back from the latest draw

Each draw is rendered as a `<div class='rowx div-link'>` block. The block holds
an onclick `result-DD-MM-YYYY.aspx` link (the authoritative day/month/Buddhist
year) followed by `row-hld` cells:

    [0] First prize          (6 digits, occasionally 7 in the source)
    [1] 2 ตัวบน  (last 2 of first prize - derivable, not stored)
    [2] 3 ตัวบน  (last 3 of first prize - derivable, not stored)
    [3] 2 ตัวล่าง = "เลขท้าย 2 ตัว" -> Last2
    [4] "3 ตัวหน้า , 3 ตัวล่าง": <u>front</u> entries + plain back entries
    [5] mobile duplicate of [3]
    [6] mobile duplicate of [4]

Era differences captured by the parser:
    * BE 2533-2557: no front-3 numbers, FOUR back-3 numbers.
    * BE 2558:      transition year (mixed old/new format).
    * BE 2559-2569: two front-3 numbers, two back-3 numbers.

The dataset therefore extends the README schema with nullable Back3_3 / Back3_4
so that no source value is discarded.
"""

from __future__ import annotations

import csv
import re
import sqlite3
import urllib.request
from dataclasses import dataclass, fields
from pathlib import Path

STATS_URL = "https://myhora.com/lottery/stats.aspx?mx=09&vx=40"
USER_AGENT = "Mozilla/5.0 (compatible; lottery-research/1.0)"
# Dates are stored verbatim in the Buddhist Era (BE) as shown on myhora.com.
# Gregorian year = BE year - 543, if ever needed downstream.

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "dataset"
CSV_PATH = DATASET_DIR / "lottery_results.csv"
SQLITE_PATH = DATASET_DIR / "lottery_results.sqlite"

_ROW_SPLIT = re.compile(r"<div class='rowx div-link'")
_RESULT_LINK = re.compile(r"result-(\d{2})-(\d{2})-(\d{4})\.aspx")
_ROW_HLD_CELL = re.compile(r"row-hld[^>]*>(.*?)</div>", re.S)
_UNDERLINE = re.compile(r"<u>(.*?)</u>", re.S)
_TAG = re.compile(r"<[^>]+>")
_THREE_DIGITS = re.compile(r"\d{3}")


@dataclass(frozen=True)
class DrawResult:
    """One lottery draw, matching the README schema (+ Back3_3/Back3_4)."""

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


def write_csv(results: list[DrawResult], path: Path = CSV_PATH) -> None:
    columns = [f.name for f in fields(DrawResult)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for record in results:
            writer.writerow([getattr(record, col) for col in columns])


def write_sqlite(results: list[DrawResult], path: Path = SQLITE_PATH) -> None:
    columns = [f.name for f in fields(DrawResult)]
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    coldefs = ", ".join(
        f"{col} {'INTEGER' if col in ('Year', 'Month') else 'TEXT'}"
        for col in columns
    )
    placeholders = ", ".join("?" for _ in columns)
    with sqlite3.connect(path) as conn:
        conn.execute(f"CREATE TABLE draws ({coldefs}, PRIMARY KEY (DrawDate))")
        conn.executemany(
            f"INSERT INTO draws ({', '.join(columns)}) VALUES ({placeholders})",
            [[getattr(r, col) for col in columns] for r in results],
        )
        conn.commit()


def main() -> None:
    print(f"Fetching {STATS_URL}")
    html = fetch_html()
    results = parse_rows(html)
    results.sort(key=lambda r: r.DrawDate)
    validate(results)

    write_csv(results)
    write_sqlite(results)

    seven_digit = sum(1 for r in results if len(r.FirstPrize) == 7)
    print(f"Parsed {len(results)} draws: {results[0].DrawDate} .. {results[-1].DrawDate}")
    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {SQLITE_PATH}")
    print(f"Note: {seven_digit} draws have a 7-digit first prize (preserved as-is).")


if __name__ == "__main__":
    main()
