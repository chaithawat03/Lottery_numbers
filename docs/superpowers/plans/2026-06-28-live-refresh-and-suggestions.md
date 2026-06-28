# Live Refresh & Experimental Suggestions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an incremental "fetch latest draws" updater and an experimental, descriptive number-suggestion engine, surfaced in both the Streamlit dashboard and a CLI.

**Architecture:** Approach A (refactor for reuse). The scraper's stdlib-only fetch/parse moves into `src/lottery/data/myhora.py`; `DrawRepository` gains `latest_date()` + `save()` (still the only writer of SQLite/CSV); a new `updater.py` orchestrates fetch → filter-new → merge → save. A pure `stats/suggest.py` computes a blended descriptive score (frequency + recency-gap + recent-trend) per prize category. A `cli.py` and dashboard tab expose both.

**Tech Stack:** Python 3.13+ (dev 3.14), pandas 3.0, numpy, scipy, plotly, streamlit, pytest, ruff. Run tests with `.venv/bin/pytest`; lint with `.venv/bin/ruff check src tests`.

## Global Constraints

- **Honesty (overrides all wording):** suggestions are *descriptive experimental scores from historical data only* — never a prediction, never "probability of being drawn", never a number presented as likely to win. Every suggestion surface must render the disclaimer adjacent to the numbers.
- Number fields (`FirstPrize`, `Last2`, `Front3_*`, `Back3_*`) stay **strings** to preserve leading zeros; empty era cells are `pandas.NA`, **never** `0` or `""` in stored/loaded frames.
- Dependency direction: `dashboard → stats → features → data`. **Only `repository` touches SQLite/CSV on disk.**
- `lottery.data.myhora` must stay **stdlib-only** (no pandas/numpy import) so the standalone scraper keeps working under system `python3`.
- pandas is **3.0** — verify API behavior, don't assume 2.x.
- Dates/years remain in the **Buddhist Era (BE)** calendar, matching the source.
- ruff: line-length 100, target py313.
- Branch: continue on `feature/foundation`.

---

### Task 1: Extract the myhora parser into the package

Move the stdlib-only fetch/parse out of the scraper so the updater can reuse it, and reduce the scraper to a thin CLI.

**Files:**
- Create: `src/lottery/data/myhora.py`
- Create: `tests/data/test_myhora.py`
- Modify: `scraper/scrape_myhora.py` (replace the moved code with an import)

**Interfaces:**
- Consumes: nothing (stdlib only).
- Produces:
  - `DrawResult` frozen dataclass with fields, in order: `DrawDate: str, Year: int, Month: int, FirstPrize: str, Last2: str, Front3_1: str, Front3_2: str, Back3_1: str, Back3_2: str, Back3_3: str, Back3_4: str`
  - `fetch_html(url: str = STATS_URL) -> str`
  - `parse_rows(html: str) -> list[DrawResult]`
  - `validate(results: list[DrawResult]) -> None`
  - `fetch_draws(url: str = STATS_URL) -> list[DrawResult]` (fetch → parse → sort by `DrawDate` → validate → return)
  - constants `STATS_URL`, `USER_AGENT`

- [ ] **Step 1: Write the failing test**

Create `tests/data/test_myhora.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/data/test_myhora.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lottery.data.myhora'`

- [ ] **Step 3: Create `src/lottery/data/myhora.py`**

```python
"""Stdlib-only fetch + parse for myhora.com lottery statistics.

Kept dependency-free (no pandas/numpy) so the standalone scraper can import it
under the system interpreter. See scraper/scrape_myhora.py for the page layout.
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
```

- [ ] **Step 4: Refactor `scraper/scrape_myhora.py` to import from the package**

Replace the moved code. The new file keeps only path setup, the CSV/SQLite writers, and `main`:

```python
"""CLI: scrape the full Thai Government Lottery history into dataset/.

Parsing/fetching now lives in lottery.data.myhora (stdlib-only). This script
is the from-scratch bootstrap; incremental updates use lottery.data.updater.
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from dataclasses import fields
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lottery.data.myhora import DrawResult, STATS_URL, fetch_draws  # noqa: E402

DATASET_DIR = PROJECT_ROOT / "dataset"
CSV_PATH = DATASET_DIR / "lottery_results.csv"
SQLITE_PATH = DATASET_DIR / "lottery_results.sqlite"


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
    results = fetch_draws()
    write_csv(results)
    write_sqlite(results)
    seven_digit = sum(1 for r in results if len(r.FirstPrize) == 7)
    print(f"Parsed {len(results)} draws: {results[0].DrawDate} .. {results[-1].DrawDate}")
    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {SQLITE_PATH}")
    print(f"Note: {seven_digit} draws have a 7-digit first prize (preserved as-is).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/data/test_myhora.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Lint**

Run: `.venv/bin/ruff check src/lottery/data/myhora.py scraper/scrape_myhora.py tests/data/test_myhora.py`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add src/lottery/data/myhora.py scraper/scrape_myhora.py tests/data/test_myhora.py
git commit -m "refactor: extract stdlib-only myhora parser into package"
```

---

### Task 2: Repository gains `latest_date()` and `save()`

`DrawRepository` becomes able to report the newest stored draw and to persist a full frame to both stores, while staying the sole disk writer.

**Files:**
- Modify: `src/lottery/data/repository.py`
- Modify: `tests/data/test_repository.py` (append tests)

**Interfaces:**
- Consumes: `ALL_COLUMNS`, `INT_COLUMNS`, `TABLE_NAME` from `lottery.data.models`.
- Produces:
  - `DrawRepository(db_path, csv_path=None)` — `csv_path` optional second arg.
  - `DrawRepository.latest_date() -> str | None`
  - `DrawRepository.save(df: pd.DataFrame) -> None` — writes SQLite (`INSERT OR REPLACE`) always, CSV only if `csv_path` is set; both sorted by `DrawDate`; `pandas.NA` persisted as NULL/empty.

- [ ] **Step 1: Write the failing tests**

Append to `tests/data/test_repository.py`:

```python
from lottery.data.models import ALL_COLUMNS as _COLS


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/data/test_repository.py -v`
Expected: FAIL — `TypeError` (two args) / `AttributeError: 'DrawRepository' object has no attribute 'latest_date'`

- [ ] **Step 3: Implement in `src/lottery/data/repository.py`**

Change the import line to include `INT_COLUMNS` (already imported). Replace the `__init__` and add the two methods:

```python
    def __init__(self, db_path: Path | str, csv_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path)
        self.csv_path = Path(csv_path) if csv_path else None
```

Add these methods to the class (after `load`):

```python
    def latest_date(self) -> str | None:
        if not self.db_path.exists():
            return None
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(f"SELECT MAX(DrawDate) FROM {TABLE_NAME}").fetchone()
        return row[0] if row and row[0] is not None else None

    def save(self, df: pd.DataFrame) -> None:
        out = df.sort_values("DrawDate").reset_index(drop=True)[ALL_COLUMNS].copy()
        coldefs = ", ".join(
            f"{c} {'INTEGER' if c in INT_COLUMNS else 'TEXT'}" for c in ALL_COLUMNS
        )
        placeholders = ", ".join("?" for _ in ALL_COLUMNS)
        records = [
            [None if pd.isna(v) else v for v in row]
            for row in out.itertuples(index=False, name=None)
        ]
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} "
                f"({coldefs}, PRIMARY KEY (DrawDate))"
            )
            conn.executemany(
                f"INSERT OR REPLACE INTO {TABLE_NAME} "
                f"({', '.join(ALL_COLUMNS)}) VALUES ({placeholders})",
                records,
            )
            conn.commit()
        if self.csv_path is not None:
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            out.to_csv(self.csv_path, index=False)
        logger.info("Saved %d draws to %s", len(out), self.db_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/data/test_repository.py -v`
Expected: PASS (existing 3 + new 3)

- [ ] **Step 5: Lint**

Run: `.venv/bin/ruff check src/lottery/data/repository.py tests/data/test_repository.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/lottery/data/repository.py tests/data/test_repository.py
git commit -m "feat: repository latest_date() and save() (CSV + SQLite)"
```

---

### Task 3: Incremental updater

Orchestrate fetching the latest draws and merging only new ones into the dataset.

**Files:**
- Create: `src/lottery/data/updater.py`
- Create: `tests/data/test_updater.py`

**Interfaces:**
- Consumes: `DrawResult`, `fetch_draws` from `lottery.data.myhora`; `ALL_COLUMNS`, `INT_COLUMNS`, `NUMBER_COLUMNS` from `lottery.data.models`; `DrawRepository` from `lottery.data.repository`.
- Produces:
  - `class UpdateError(Exception)`
  - `@dataclass UpdateReport` with `added: int`, `latest_before: str | None`, `latest_after: str | None`, `new_dates: list[str]`
  - `update_dataset(repo: DrawRepository, *, source: Callable[[], list[DrawResult]] = fetch_draws) -> UpdateReport`

- [ ] **Step 1: Write the failing tests**

Create `tests/data/test_updater.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/data/test_updater.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lottery.data.updater'`

- [ ] **Step 3: Create `src/lottery/data/updater.py`**

```python
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from lottery.data.models import ALL_COLUMNS, INT_COLUMNS, NUMBER_COLUMNS
from lottery.data.myhora import DrawResult, fetch_draws
from lottery.data.repository import DrawRepository

logger = logging.getLogger(__name__)


class UpdateError(Exception):
    """Raised when fetching/refreshing the dataset fails."""


@dataclass
class UpdateReport:
    added: int
    latest_before: str | None
    latest_after: str | None
    new_dates: list[str]


def _to_frame(results: list[DrawResult]) -> pd.DataFrame:
    rows = [{name: getattr(r, name) for name in ALL_COLUMNS} for r in results]
    df = pd.DataFrame(rows, columns=ALL_COLUMNS)
    for col in NUMBER_COLUMNS:
        df[col] = df[col].astype("string").replace({"": pd.NA})
    for col in INT_COLUMNS:
        df[col] = df[col].astype("int64")
    return df


def update_dataset(
    repo: DrawRepository,
    *,
    source: Callable[[], list[DrawResult]] = fetch_draws,
) -> UpdateReport:
    """Fetch from `source`, merge only draws newer than the latest stored one."""
    latest_before = repo.latest_date()
    try:
        fetched = _to_frame(source())
    except Exception as exc:  # noqa: BLE001 - re-raised as a domain error
        raise UpdateError(f"Failed to fetch latest draws: {exc}") from exc

    if latest_before is not None:
        new = fetched[fetched["DrawDate"] > latest_before]
    else:
        new = fetched

    if new.empty:
        logger.info("Dataset already up to date (latest %s)", latest_before)
        return UpdateReport(0, latest_before, latest_before, [])

    existing = (
        repo.load() if latest_before is not None
        else pd.DataFrame(columns=ALL_COLUMNS)
    )
    merged = (
        pd.concat([existing, new], ignore_index=True)
        .drop_duplicates(subset="DrawDate", keep="first")
        .sort_values("DrawDate")
        .reset_index(drop=True)
    )
    repo.save(merged)

    new_dates = sorted(new["DrawDate"].tolist())
    latest_after = merged["DrawDate"].max()
    logger.info("Added %d new draws (%s -> %s)", len(new_dates), latest_before, latest_after)
    return UpdateReport(len(new_dates), latest_before, latest_after, new_dates)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/data/test_updater.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Lint**

Run: `.venv/bin/ruff check src/lottery/data/updater.py tests/data/test_updater.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/lottery/data/updater.py tests/data/test_updater.py
git commit -m "feat: incremental dataset updater"
```

---

### Task 4: Config gains `[suggest]` settings

Add tunable suggestion settings and clean the stray commented-out experiments left in `config.py`.

**Files:**
- Modify: `config/config.toml`
- Modify: `src/lottery/config.py`
- Modify: `tests/test_config.py` (append a test)

**Interfaces:**
- Produces: `Config` dataclass with three new fields — `top_n: int`, `recent_window: int`, `weights: dict[str, float]`. `load_config` reads them from the `[suggest]` table with defaults `top_n=10`, `recent_window=50`, `weights={"frequency":0.5,"recency":0.25,"trend":0.25}`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config.py`:

```python
def test_load_config_reads_suggest_section():
    from lottery.config import load_config

    cfg = load_config()
    assert cfg.top_n == 10
    assert cfg.recent_window == 50
    assert cfg.weights["frequency"] == 0.5
    assert set(cfg.weights) == {"frequency", "recency", "trend"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_config.py::test_load_config_reads_suggest_section -v`
Expected: FAIL with `AttributeError: 'Config' object has no attribute 'top_n'`

- [ ] **Step 3: Add the `[suggest]` table to `config/config.toml`**

Append:

```toml
[suggest]
top_n = 10
recent_window = 50

[suggest.weights]
frequency = 0.5
recency = 0.25
trend = 0.25
```

- [ ] **Step 4: Update `src/lottery/config.py`**

Remove the stray commented lines (the `current_dir*` block and the `print(...)` line) around `DEFAULT_CONFIG_PATH`, leaving a single clean definition. Then extend the dataclass and loader:

```python
@dataclass(frozen=True)
class Config:
    db_path: Path
    csv_path: Path
    default_window: int
    log_level: str
    top_n: int
    recent_window: int
    weights: dict[str, float]
```

In `load_config`, before the `return`:

```python
    suggest = data.get("suggest", {})
    default_weights = {"frequency": 0.5, "recency": 0.25, "trend": 0.25}
    weights = {k: float(v) for k, v in suggest.get("weights", default_weights).items()}
```

and extend the returned `Config(...)` with:

```python
        top_n=int(suggest.get("top_n", 10)),
        recent_window=int(suggest.get("recent_window", 50)),
        weights=weights,
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: PASS (existing + new test)

- [ ] **Step 6: Lint**

Run: `.venv/bin/ruff check src/lottery/config.py tests/test_config.py`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add config/config.toml src/lottery/config.py tests/test_config.py
git commit -m "feat: config [suggest] settings; tidy config.py"
```

---

### Task 5: Blended candidate scoring

Pure scoring of one series into normalized frequency/recency/trend components and a weighted total.

**Files:**
- Create: `src/lottery/stats/suggest.py`
- Create: `tests/stats/test_suggest.py`

**Interfaces:**
- Consumes: `frequency`, `current_gap` from `lottery.stats.frequency`.
- Produces:
  - `DISCLAIMER: str` (Thai + English)
  - `DEFAULT_WEIGHTS: dict[str, float]`
  - `score_candidates(series: pd.Series, *, weights: dict[str, float] | None = None, recent_window: int = 50) -> pd.DataFrame` with columns `["value", "freq_score", "recency_score", "trend_score", "score"]`, sorted by `score` descending; empty/all-NA input → empty frame with those columns.

- [ ] **Step 1: Write the failing tests**

Create `tests/stats/test_suggest.py`:

```python
import pandas as pd

from lottery.stats.suggest import DISCLAIMER, score_candidates

COLS = ["value", "freq_score", "recency_score", "trend_score", "score"]


def test_disclaimer_mentions_random_and_not_prediction():
    assert "สุ่ม" in DISCLAIMER
    assert "prediction" in DISCLAIMER.lower()


def test_empty_series_returns_empty_frame_with_columns():
    out = score_candidates(pd.Series([], dtype="string"))
    assert list(out.columns) == COLS
    assert out.empty


def test_frequency_weight_orders_by_count():
    s = pd.Series(["01", "01", "01", "02", "03", "03"])
    out = score_candidates(
        s, weights={"frequency": 1.0, "recency": 0.0, "trend": 0.0}, recent_window=10
    )
    assert list(out.columns) == COLS
    assert out.iloc[0]["value"] == "01"
    assert out.iloc[0]["freq_score"] == 1.0


def test_recency_weight_prefers_most_recent():
    s = pd.Series(["01", "02", "02", "03", "02"])  # 02 drawn most recently
    out = score_candidates(
        s, weights={"frequency": 0.0, "recency": 1.0, "trend": 0.0}
    )
    assert out.iloc[0]["value"] == "02"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/stats/test_suggest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lottery.stats.suggest'`

- [ ] **Step 3: Create `src/lottery/stats/suggest.py`**

```python
"""Experimental, descriptive number scoring.

THESE ARE NOT PREDICTIONS. The lottery is a near-uniform random draw; past
results cannot predict future ones. Scores rank candidates by historical
signals only and exist for educational/descriptive purposes.
"""

from __future__ import annotations

import pandas as pd

from lottery.stats.frequency import current_gap, frequency

DISCLAIMER = (
    "ℹ️ ตัวเลขเหล่านี้เป็นคะแนนจากสถิติย้อนหลังเพื่อการศึกษาเท่านั้น ไม่ใช่การทำนาย "
    "หวยเป็นการสุ่ม ผลในอดีตไม่สามารถทำนายผลในอนาคตได้ "
    "(Experimental scores from historical statistics only — not a prediction. "
    "The lottery is random; past results cannot predict the future.)"
)

DEFAULT_WEIGHTS = {"frequency": 0.5, "recency": 0.25, "trend": 0.25}

_SCORE_COLUMNS = ["value", "freq_score", "recency_score", "trend_score", "score"]


def _normalize(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    if hi == lo:
        return pd.Series(0.0, index=s.index)
    return (s - lo) / (hi - lo)


def score_candidates(
    series: pd.Series,
    *,
    weights: dict[str, float] | None = None,
    recent_window: int = 50,
) -> pd.DataFrame:
    """Score each distinct value by blended frequency/recency/trend signals."""
    weights = weights or DEFAULT_WEIGHTS
    s = series.dropna()
    if s.empty:
        return pd.DataFrame(columns=_SCORE_COLUMNS)

    freq = frequency(s)[["value", "count"]]
    gap = current_gap(s)  # columns: value, gap
    recent_counts = s.tail(recent_window).value_counts()

    df = freq.merge(gap, on="value", how="left")
    df["gap"] = df["gap"].fillna(df["gap"].max())
    df["trend"] = df["value"].map(recent_counts).fillna(0)

    df["freq_score"] = _normalize(df["count"])
    df["recency_score"] = _normalize(df["gap"].max() - df["gap"])
    df["trend_score"] = _normalize(df["trend"])
    df["score"] = (
        weights["frequency"] * df["freq_score"]
        + weights["recency"] * df["recency_score"]
        + weights["trend"] * df["trend_score"]
    )
    return (
        df.sort_values("score", ascending=False)
        .reset_index(drop=True)[_SCORE_COLUMNS]
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/stats/test_suggest.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Lint**

Run: `.venv/bin/ruff check src/lottery/stats/suggest.py tests/stats/test_suggest.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/lottery/stats/suggest.py tests/stats/test_suggest.py
git commit -m "feat: blended candidate scoring (frequency/recency/trend)"
```

---

### Task 6: Per-category suggestions

Build the right series per prize category and assemble all suggestions.

**Files:**
- Modify: `src/lottery/stats/suggest.py`
- Modify: `tests/stats/test_suggest.py` (append)

**Interfaces:**
- Consumes: `score_candidates` (same module).
- Produces:
  - `CATEGORIES: list[str]` = `["last2", "back3", "front3", "firstprize_last3"]`
  - `suggest_category(df, category, *, weights=None, recent_window=50, top_n=10) -> pd.DataFrame` (top-N rows of `score_candidates`)
  - `firstprize_digit_frequency(df) -> pd.DataFrame` with columns `["position", "digit", "count"]` (positions 1–6, six-digit prizes only)
  - `suggest_all(df, *, weights=None, recent_window=50, top_n=10) -> dict[str, pd.DataFrame]` keyed by each category plus `"firstprize_digits"`

- [ ] **Step 1: Write the failing tests**

Append to `tests/stats/test_suggest.py`:

```python
from lottery.stats.suggest import (
    CATEGORIES,
    firstprize_digit_frequency,
    suggest_all,
    suggest_category,
)

ALL_COLS = [
    "DrawDate", "Year", "Month", "FirstPrize", "Last2",
    "Front3_1", "Front3_2", "Back3_1", "Back3_2", "Back3_3", "Back3_4",
]


def _sample_df():
    return pd.DataFrame(
        [
            ["2569-06-01", 2569, 6, "111222", "22", pd.NA, pd.NA, "777", "888", pd.NA, pd.NA],
            ["2569-06-16", 2569, 6, "111333", "33", "434", "758", "777", "999", pd.NA, pd.NA],
        ],
        columns=ALL_COLS,
    )


def test_suggest_category_back3_combines_columns():
    out = suggest_category(_sample_df(), "back3", top_n=5)
    # "777" appears in Back3_1 of both rows -> highest count
    assert out.iloc[0]["value"] == "777"


def test_suggest_category_top_n_limits_rows():
    out = suggest_category(_sample_df(), "last2", top_n=1)
    assert len(out) == 1


def test_firstprize_digit_frequency_shape():
    out = firstprize_digit_frequency(_sample_df())
    assert list(out.columns) == ["position", "digit", "count"]
    # position 1 is "1" in both six-digit prizes
    pos1 = out[(out["position"] == 1) & (out["digit"] == "1")]
    assert pos1.iloc[0]["count"] == 2


def test_suggest_all_has_every_category():
    out = suggest_all(_sample_df(), top_n=3)
    for cat in CATEGORIES:
        assert cat in out
    assert "firstprize_digits" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/stats/test_suggest.py -v`
Expected: FAIL with `ImportError: cannot import name 'CATEGORIES'`

- [ ] **Step 3: Append to `src/lottery/stats/suggest.py`**

```python
_BACK3_COLS = ["Back3_1", "Back3_2", "Back3_3", "Back3_4"]
_FRONT3_COLS = ["Front3_1", "Front3_2"]

CATEGORIES = ["last2", "back3", "front3", "firstprize_last3"]


def _category_series(df: pd.DataFrame, category: str) -> pd.Series:
    if category == "last2":
        return df["Last2"]
    if category == "back3":
        return pd.concat([df[c] for c in _BACK3_COLS], ignore_index=True)
    if category == "front3":
        return pd.concat([df[c] for c in _FRONT3_COLS], ignore_index=True)
    if category == "firstprize_last3":
        return df["FirstPrize"].dropna().astype("string").str[-3:]
    raise ValueError(f"Unknown category: {category}")


def suggest_category(
    df: pd.DataFrame,
    category: str,
    *,
    weights: dict[str, float] | None = None,
    recent_window: int = 50,
    top_n: int = 10,
) -> pd.DataFrame:
    series = _category_series(df, category)
    scored = score_candidates(series, weights=weights, recent_window=recent_window)
    return scored.head(top_n).reset_index(drop=True)


def firstprize_digit_frequency(df: pd.DataFrame) -> pd.DataFrame:
    fp = df["FirstPrize"].dropna().astype("string")
    fp = fp[fp.str.len() == 6]
    rows = []
    for pos in range(6):
        counts = fp.str[pos].value_counts()
        for digit, count in counts.items():
            rows.append({"position": pos + 1, "digit": digit, "count": int(count)})
    return (
        pd.DataFrame(rows, columns=["position", "digit", "count"])
        .sort_values(["position", "digit"])
        .reset_index(drop=True)
    )


def suggest_all(
    df: pd.DataFrame,
    *,
    weights: dict[str, float] | None = None,
    recent_window: int = 50,
    top_n: int = 10,
) -> dict[str, pd.DataFrame]:
    out = {
        cat: suggest_category(
            df, cat, weights=weights, recent_window=recent_window, top_n=top_n
        )
        for cat in CATEGORIES
    }
    out["firstprize_digits"] = firstprize_digit_frequency(df)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/stats/test_suggest.py -v`
Expected: PASS (8 tests total)

- [ ] **Step 5: Lint**

Run: `.venv/bin/ruff check src/lottery/stats/suggest.py tests/stats/test_suggest.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/lottery/stats/suggest.py tests/stats/test_suggest.py
git commit -m "feat: per-category suggestions + firstprize digit frequency"
```

---

### Task 7: CLI (`update` / `suggest`)

A small argparse dispatcher runnable as `python -m lottery.cli <command>`.

**Files:**
- Create: `src/lottery/cli.py`
- Create: `tests/test_cli.py`
- Modify: `pyproject.toml` (add `[project.scripts]`)

**Interfaces:**
- Consumes: `load_config`; `DrawRepository`; `update_dataset`, `UpdateError`; `suggest_all`, `DISCLAIMER`, `CATEGORIES`.
- Produces: `main(argv: list[str] | None = None) -> int`. Subcommands `update` (runs updater, prints report, returns 0 / 1 on `UpdateError`) and `suggest` (prints top-N per category + `DISCLAIMER`, returns 0).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli.py`:

```python
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
```

(The `suggest` command reads the committed dataset read-only — safe in tests. `update` is covered by Task 3's updater tests and is not exercised here to avoid network.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lottery.cli'`

- [ ] **Step 3: Create `src/lottery/cli.py`**

```python
from __future__ import annotations

import argparse

from lottery.config import load_config
from lottery.data.repository import DrawRepository
from lottery.data.updater import UpdateError, update_dataset
from lottery.stats.suggest import CATEGORIES, DISCLAIMER, suggest_all


def _cmd_update(cfg) -> int:
    repo = DrawRepository(cfg.db_path, cfg.csv_path)
    try:
        report = update_dataset(repo)
    except UpdateError as exc:
        print(f"Update failed: {exc}")
        return 1
    if report.added == 0:
        print(f"Already up to date (latest {report.latest_before}).")
    else:
        print(f"Added {report.added} draw(s): {report.latest_before} -> {report.latest_after}")
        for date in report.new_dates:
            print(f"  + {date}")
    return 0


def _cmd_suggest(cfg) -> int:
    df = DrawRepository(cfg.db_path).load()
    results = suggest_all(
        df, weights=cfg.weights, recent_window=cfg.recent_window, top_n=cfg.top_n
    )
    for cat in CATEGORIES:
        print(f"\n=== {cat} (top {cfg.top_n}) ===")
        print(results[cat].to_string(index=False))
    print("\n" + DISCLAIMER)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lottery")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("update", help="Fetch and merge the latest draws")
    sub.add_parser("suggest", help="Print experimental per-category suggestions")
    args = parser.parse_args(argv)

    cfg = load_config()
    if args.command == "update":
        return _cmd_update(cfg)
    if args.command == "suggest":
        return _cmd_suggest(cfg)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add `[project.scripts]` to `pyproject.toml`**

After the `[project.optional-dependencies]` block:

```toml
[project.scripts]
lottery = "lottery.cli:main"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Lint**

Run: `.venv/bin/ruff check src/lottery/cli.py tests/test_cli.py`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add src/lottery/cli.py tests/test_cli.py pyproject.toml
git commit -m "feat: lottery CLI (update / suggest)"
```

---

### Task 8: Dashboard — refresh button + Suggestions tab

Add a suggestion bar-chart builder (unit-tested) and wire the refresh button and a Suggestions tab into the Streamlit app.

**Files:**
- Modify: `src/lottery/dashboard/components/charts.py`
- Modify: `tests/dashboard/test_charts.py` (append)
- Modify: `src/lottery/dashboard/app.py`

**Interfaces:**
- Consumes: `score_candidates`/`suggest_all` output frames; `update_dataset`, `UpdateError`; `load_config`.
- Produces: `suggestion_bar(df: pd.DataFrame, title: str) -> go.Figure` in `charts.py`.

- [ ] **Step 1: Write the failing test**

Append to `tests/dashboard/test_charts.py`:

```python
def test_suggestion_bar_builds_figure():
    import pandas as pd

    from lottery.dashboard.components.charts import suggestion_bar

    df = pd.DataFrame(
        {"value": ["01", "02"], "score": [0.9, 0.4]},
    )
    fig = suggestion_bar(df, "scores")
    assert fig.layout.title.text == "scores"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/dashboard/test_charts.py::test_suggestion_bar_builds_figure -v`
Expected: FAIL with `ImportError: cannot import name 'suggestion_bar'`

- [ ] **Step 3: Add `suggestion_bar` to `charts.py`**

```python
def suggestion_bar(df: pd.DataFrame, title: str) -> go.Figure:
    return px.bar(df, x="value", y="score", title=title)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/dashboard/test_charts.py -v`
Expected: PASS

- [ ] **Step 5: Wire the refresh button and Suggestions tab into `app.py`**

Add to the chart-builder import block:

```python
from lottery.dashboard.components.charts import (
    frequency_bar,
    heatmap_10x10,
    suggestion_bar,
    transition_heatmap,
)
```

Add to the stats import line:

```python
from lottery.stats import digits, frequency, pairs, sequence, suggest, summary
```

In `main()`, right after `df = get_data()`, load config and add the sidebar refresh button:

```python
    cfg = load_config()
    if st.sidebar.button("🔄 อัปเดตข้อมูลล่าสุด"):
        from lottery.data.updater import UpdateError, update_dataset

        repo = DrawRepository(cfg.db_path, cfg.csv_path)
        try:
            with st.spinner("กำลังดึงข้อมูลงวดล่าสุด..."):
                report = update_dataset(repo)
            get_data.clear()
            if report.added:
                st.sidebar.success(
                    f"เพิ่ม {report.added} งวด ({report.latest_before} → {report.latest_after})"
                )
            else:
                st.sidebar.info("ข้อมูลเป็นปัจจุบันแล้ว")
        except UpdateError as exc:
            st.sidebar.error(f"อัปเดตไม่สำเร็จ: {exc}")
```

Change the tabs list to add a seventh tab:

```python
    tabs = st.tabs(
        ["ภาพรวม", "ความถี่", "ช่วงห่าง", "หลักตัวเลข", "คู่/สามตัว", "แนวโน้ม", "ตัวเลขน่าสนใจ"]
    )
```

At the end of `main()` (after the `with tabs[5]:` block), add the Suggestions tab. It uses the full `df` (all history), independent of the year filter:

```python
    with tabs[6]:
        st.warning(suggest.DISCLAIMER)
        results = suggest.suggest_all(
            df, weights=cfg.weights, recent_window=cfg.recent_window, top_n=cfg.top_n
        )
        labels = {
            "last2": "เลขท้าย 2 ตัว",
            "back3": "เลขท้าย 3 ตัว",
            "front3": "เลขหน้า 3 ตัว",
            "firstprize_last3": "3 ตัวท้ายรางวัลที่ 1",
        }
        for cat, label in labels.items():
            st.subheader(label)
            cand = results[cat]
            if cand.empty:
                st.info("ไม่มีข้อมูลเพียงพอสำหรับประเภทนี้")
                continue
            st.plotly_chart(
                suggestion_bar(cand, f"คะแนนเชิงสถิติ {label}"),
                use_container_width=True,
            )
            st.dataframe(cand)
        st.subheader("ความถี่ตัวเลขแต่ละหลัก (รางวัลที่ 1)")
        st.dataframe(results["firstprize_digits"])
```

- [ ] **Step 6: Lint and run the full suite**

Run: `.venv/bin/ruff check src tests && .venv/bin/pytest`
Expected: `All checks passed!` and all tests PASS.

- [ ] **Step 7: Manual dashboard smoke check**

Run: `PYTHONPATH=src .venv/bin/streamlit run src/lottery/dashboard/app.py`
Verify: the **🔄 อัปเดตข้อมูลล่าสุด** button shows "ข้อมูลเป็นปัจจุบันแล้ว" (or adds draws), and the **ตัวเลขน่าสนใจ** tab renders the disclaimer banner, four category bar charts/tables, and the first-prize digit table. (Browser verification is a human step.)

- [ ] **Step 8: Commit**

```bash
git add src/lottery/dashboard/components/charts.py tests/dashboard/test_charts.py src/lottery/dashboard/app.py
git commit -m "feat: dashboard refresh button + suggestions tab"
```

---

## Self-Review

**Spec coverage:**
- Honesty framing → `DISCLAIMER` (Task 5), rendered in CLI (Task 7) and dashboard tab (Task 8); score column named `score`. ✅
- #1 incremental refresh → `myhora.fetch_draws` (T1), `repository.latest_date/save` (T2), `updater.update_dataset` (T3). ✅
- #2 suggestions, all categories → `score_candidates` (T5), `suggest_category`/`firstprize_digit_frequency`/`suggest_all` for last2/back3/front3/firstprize_last3/digits (T6). ✅
- Blended score + breakdown, configurable weights → `score_candidates` columns + `[suggest]` config (T4/T5). ✅
- Surface dashboard + CLI → T7 + T8. ✅
- Errors: `UpdateError` (T3) caught in CLI (T7) and dashboard (T8); empty category → empty frame → "ไม่มีข้อมูลเพียงพอ" (T6/T8). ✅
- Testing per spec → tasks include parse, repository roundtrip, updater idempotency/error, scoring math, category construction, chart smoke. ✅
- stdlib-only `myhora` → no pandas import in T1; scraper imports it. ✅

**Placeholder scan:** No TBD/TODO; every code step shows complete code; no "handle edge cases" hand-waves (empty/NA paths are concrete). ✅

**Type consistency:** `DrawResult` field order matches `ALL_COLUMNS`; `update_dataset(repo, *, source)` signature consistent T3↔T7↔T8; `score_candidates`/`suggest_*` kwargs (`weights`, `recent_window`, `top_n`) identical across T5/T6/T7/T8; `_SCORE_COLUMNS` matches the asserted column list; `DrawRepository(db_path, csv_path=None)` used consistently. ✅
