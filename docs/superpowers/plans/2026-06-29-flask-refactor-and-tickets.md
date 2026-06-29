# Flask Refactor + My Tickets — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Streamlit dashboard with a Flask + HTML + Plotly.js web app at full feature parity, and add a "My Tickets" page that records bought tickets to JSON with win/loss, spending, and suggestion-overlap analysis.

**Architecture:** Flask application factory + two blueprints (`analysis`, `tickets`). Pages are Jinja shells; a JSON API returns Plotly figure dicts + table records that vanilla JS renders with Plotly.js. The pure `data → features → stats` layers are untouched; new pure modules `tickets/store.py` (JSON persistence) and `stats/tickets.py` (analysis) sit beside them. Dependency direction: `web → stats/tickets → tickets/store → data`.

**Tech Stack:** Python 3.13+, Flask, Plotly (figure construction server-side, Plotly.js render client-side), pandas 3.0, pytest, ruff.

## Global Constraints

- Python ≥ 3.13 (developed on 3.14). Type hints, PEP8, `ruff` (line-length 100, `target-version = "py313"`).
- Dependencies live in the project venv: install with `.venv/bin/pip`, run tests with `.venv/bin/pytest`, lint with `.venv/bin/ruff check src tests`. pandas is **3.0** (not 2.x).
- Number fields (`FirstPrize`, `Last2`, `Front3_*`, `Back3_*`) are **strings** to preserve leading zeros; empty-era cells are `pandas.NA`, never `0`. Ticket `number` is likewise a string.
- Dates/years are **Buddhist Era (BE)**, matching the dataset and source.
- **Honesty rule:** all analysis is descriptive/experimental. The non-predictive DISCLAIMER must render on every page, on the suggestions panel, and near any winnings/net figure. Never present a number as likely to be drawn. Reuse `lottery.stats.suggest.DISCLAIMER`.
- `tickets/store.py` is the **sole writer** of `dataset/my_tickets.json`; the file is git-ignored.
- Run command after refactor: `PYTHONPATH=src .venv/bin/flask --app lottery.web run`.
- Category vocabulary for tickets is exactly `Last2 | Back3 | Front3 | FirstPrize`.

---

### Task 1: Dependencies, config, and gitignore

**Files:**
- Modify: `pyproject.toml` (deps)
- Modify: `config/config.toml`
- Modify: `src/lottery/config.py`
- Modify: `.gitignore`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` gains `tickets_path: Path` and `payout: dict[str, float]` (keys `ticket_unit`, `Last2`, `Back3`, `Front3`, `FirstPrize`). Env overrides: `LOTTERY_TICKETS_PATH`.

- [ ] **Step 1: Install Flask, drop Streamlit from deps**

Edit `pyproject.toml` `dependencies`: remove the `"streamlit>=1.36",` line and add `"flask>=3.0",`. Then:

```bash
.venv/bin/pip install "flask>=3.0"
.venv/bin/pip uninstall -y streamlit
```

- [ ] **Step 2: Add config sections**

Append to `config/config.toml`:

```toml
[paths]
# (existing db_path / csv_path stay) — add:
tickets_path = "dataset/my_tickets.json"

[payout]            # standard official payout per single 80-baht ticket
ticket_unit = 80
Last2 = 2000
Back3 = 4000
Front3 = 4000
FirstPrize = 6000000
```

(Place `tickets_path` under the existing `[paths]` table; add the new `[payout]` table at the end.)

- [ ] **Step 3: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_config_loads_tickets_path_and_payout(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        """
[paths]
db_path = "dataset/lottery_results.sqlite"
csv_path = "dataset/lottery_results.csv"
tickets_path = "dataset/my_tickets.json"
[analysis]
default_window = 100
[logging]
level = "INFO"
[suggest]
top_n = 10
recent_window = 50
[suggest.weights]
frequency = 0.5
recency = 0.25
trend = 0.25
[payout]
ticket_unit = 80
Last2 = 2000
Back3 = 4000
Front3 = 4000
FirstPrize = 6000000
""",
        encoding="utf-8",
    )
    monkeypatch.delenv("LOTTERY_TICKETS_PATH", raising=False)
    from lottery.config import load_config

    cfg = load_config(cfg_file)
    assert cfg.tickets_path == Path("dataset/my_tickets.json")
    assert cfg.payout["Last2"] == 2000
    assert cfg.payout["ticket_unit"] == 80
```

Ensure `from pathlib import Path` is imported in the test module.

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_config.py::test_config_loads_tickets_path_and_payout -v`
Expected: FAIL (`Config` has no attribute `tickets_path` / TypeError on construction).

- [ ] **Step 5: Implement config changes**

In `src/lottery/config.py`, add fields to the `Config` dataclass:

```python
    tickets_path: Path
    payout: dict[str, float]
```

In `load_config`, before the `return`:

```python
    payout = {k: float(v) for k, v in data.get("payout", {}).items()}
```

Add to the `Config(...)` constructor call:

```python
        tickets_path=Path(
            os.getenv("LOTTERY_TICKETS_PATH", data["paths"]["tickets_path"])
        ),
        payout=payout,
```

- [ ] **Step 6: Ignore the tickets file**

Append to `.gitignore`:

```
# Personal ticket records (My Tickets feature)
dataset/my_tickets.json
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: PASS (all config tests).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml config/config.toml src/lottery/config.py .gitignore tests/test_config.py
git commit -m "feat: add Flask dep, payout + tickets_path config"
```

---

### Task 2: Ticket model + JSON store

**Files:**
- Create: `src/lottery/tickets/__init__.py`
- Create: `src/lottery/tickets/models.py`
- Create: `src/lottery/tickets/store.py`
- Test: `tests/tickets/__init__.py`, `tests/tickets/test_store.py`

**Interfaces:**
- Produces:
  - `TicketRecord` dataclass: `id: str`, `number: str`, `category: str`, `draw_date: str`, `price: float`, `created_at: str`; methods `to_dict() -> dict`, classmethod `from_dict(d: dict) -> TicketRecord`, classmethod `new(number, category, draw_date, price) -> TicketRecord` (generates `id=uuid4 hex`, `created_at=datetime.now(UTC).isoformat()`).
  - `store.load(path: Path) -> list[TicketRecord]` (missing/empty → `[]`).
  - `store.save(path: Path, records: list[TicketRecord]) -> None`.
  - `store.add(path: Path, record: TicketRecord) -> None`.
  - `store.delete(path: Path, ticket_id: str) -> bool` (True if removed, False if not found).

- [ ] **Step 1: Write the failing test**

Create `tests/tickets/__init__.py` (empty) and `tests/tickets/test_store.py`:

```python
from pathlib import Path

from lottery.tickets.models import TicketRecord
from lottery.tickets import store


def test_new_record_has_id_and_preserves_leading_zero():
    rec = TicketRecord.new(number="05", category="Last2", draw_date="2569-06-16", price=80.0)
    assert rec.number == "05"
    assert rec.id
    assert rec.created_at


def test_load_missing_file_returns_empty(tmp_path):
    assert store.load(tmp_path / "nope.json") == []


def test_save_load_roundtrip_preserves_strings(tmp_path):
    path = tmp_path / "t.json"
    rec = TicketRecord.new(number="07", category="Last2", draw_date="2569-06-16", price=80.0)
    store.save(path, [rec])
    loaded = store.load(path)
    assert len(loaded) == 1
    assert loaded[0].number == "07"
    assert loaded[0].id == rec.id


def test_add_then_delete(tmp_path):
    path = tmp_path / "t.json"
    rec = TicketRecord.new(number="23", category="Last2", draw_date="2569-06-16", price=80.0)
    store.add(path, rec)
    assert len(store.load(path)) == 1
    assert store.delete(path, rec.id) is True
    assert store.load(path) == []
    assert store.delete(path, "missing") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/tickets/test_store.py -v`
Expected: FAIL (ModuleNotFoundError: lottery.tickets).

- [ ] **Step 3: Implement model and store**

Create `src/lottery/tickets/__init__.py` (empty).

Create `src/lottery/tickets/models.py`:

```python
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

CATEGORIES = ("Last2", "Back3", "Front3", "FirstPrize")


@dataclass(frozen=True)
class TicketRecord:
    id: str
    number: str
    category: str
    draw_date: str
    price: float
    created_at: str

    @classmethod
    def new(cls, *, number: str, category: str, draw_date: str, price: float) -> "TicketRecord":
        return cls(
            id=uuid.uuid4().hex,
            number=str(number),
            category=category,
            draw_date=draw_date,
            price=float(price),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TicketRecord":
        return cls(
            id=str(d["id"]),
            number=str(d["number"]),
            category=str(d["category"]),
            draw_date=str(d["draw_date"]),
            price=float(d["price"]),
            created_at=str(d["created_at"]),
        )
```

Create `src/lottery/tickets/store.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from lottery.tickets.models import TicketRecord


def load(path: Path) -> list[TicketRecord]:
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [TicketRecord.from_dict(d) for d in data]


def save(path: Path, records: list[TicketRecord]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [r.to_dict() for r in records]
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add(path: Path, record: TicketRecord) -> None:
    records = load(path)
    records.append(record)
    save(path, records)


def delete(path: Path, ticket_id: str) -> bool:
    records = load(path)
    remaining = [r for r in records if r.id != ticket_id]
    if len(remaining) == len(records):
        return False
    save(path, remaining)
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/tickets/test_store.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lottery/tickets tests/tickets
git commit -m "feat: ticket model + JSON store"
```

---

### Task 3: Win/loss evaluation

**Files:**
- Create: `src/lottery/stats/tickets.py`
- Test: `tests/stats/test_tickets.py`

**Interfaces:**
- Consumes: `TicketRecord` (Task 2); draws `DataFrame` with columns `DrawDate`, `Last2`, `Front3_1/2`, `Back3_1..4`, `FirstPrize` (strings, `pandas.NA` for empty).
- Produces:
  - `CATEGORY_COLUMNS: dict[str, list[str]]` mapping each category to its draw columns.
  - `evaluate_ticket(record: TicketRecord, draws: pd.DataFrame, payout: dict[str, float]) -> dict` returning `{"status": "hit"|"miss"|"unknown", "matched_field": str|None, "winnings": float}`. `unknown` when `draw_date` not present in `draws`.

- [ ] **Step 1: Write the failing test**

Create `tests/stats/test_tickets.py`:

```python
import pandas as pd

from lottery.tickets.models import TicketRecord
from lottery.stats import tickets as T

PAYOUT = {"ticket_unit": 80, "Last2": 2000, "Back3": 4000, "Front3": 4000, "FirstPrize": 6000000}


def _draws():
    return pd.DataFrame(
        {
            "DrawDate": ["2569-06-16"],
            "Last2": pd.array(["23"], dtype="string"),
            "Front3_1": pd.array(["123"], dtype="string"),
            "Front3_2": pd.array(["456"], dtype="string"),
            "Back3_1": pd.array(["789"], dtype="string"),
            "Back3_2": pd.array(["780"], dtype="string"),
            "Back3_3": pd.array([pd.NA], dtype="string"),
            "Back3_4": pd.array([pd.NA], dtype="string"),
            "FirstPrize": pd.array(["112233"], dtype="string"),
        }
    )


def test_last2_hit_pays_scaled_by_price():
    rec = TicketRecord.new(number="23", category="Last2", draw_date="2569-06-16", price=160.0)
    out = T.evaluate_ticket(rec, _draws(), PAYOUT)
    assert out["status"] == "hit"
    assert out["matched_field"] == "Last2"
    assert out["winnings"] == 2000 * (160.0 / 80)  # 4000.0


def test_last2_miss_pays_zero():
    rec = TicketRecord.new(number="99", category="Last2", draw_date="2569-06-16", price=80.0)
    out = T.evaluate_ticket(rec, _draws(), PAYOUT)
    assert out["status"] == "miss"
    assert out["winnings"] == 0.0


def test_back3_matches_any_of_multiple_columns():
    rec = TicketRecord.new(number="780", category="Back3", draw_date="2569-06-16", price=80.0)
    out = T.evaluate_ticket(rec, _draws(), PAYOUT)
    assert out["status"] == "hit"
    assert out["matched_field"] == "Back3_2"


def test_firstprize_exact_match():
    rec = TicketRecord.new(number="112233", category="FirstPrize", draw_date="2569-06-16", price=80.0)
    out = T.evaluate_ticket(rec, _draws(), PAYOUT)
    assert out["status"] == "hit"
    assert out["winnings"] == 6000000.0


def test_unknown_draw_date():
    rec = TicketRecord.new(number="23", category="Last2", draw_date="2500-01-01", price=80.0)
    out = T.evaluate_ticket(rec, _draws(), PAYOUT)
    assert out["status"] == "unknown"
    assert out["winnings"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/stats/test_tickets.py -v`
Expected: FAIL (ModuleNotFoundError: lottery.stats.tickets).

- [ ] **Step 3: Implement evaluation**

Create `src/lottery/stats/tickets.py`:

```python
from __future__ import annotations

import pandas as pd

CATEGORY_COLUMNS: dict[str, list[str]] = {
    "Last2": ["Last2"],
    "Back3": ["Back3_1", "Back3_2", "Back3_3", "Back3_4"],
    "Front3": ["Front3_1", "Front3_2"],
    "FirstPrize": ["FirstPrize"],
}


def evaluate_ticket(record, draws: pd.DataFrame, payout: dict[str, float]) -> dict:
    rows = draws[draws["DrawDate"] == record.draw_date]
    if rows.empty:
        return {"status": "unknown", "matched_field": None, "winnings": 0.0}

    row = rows.iloc[0]
    matched_field = None
    for col in CATEGORY_COLUMNS.get(record.category, []):
        cell = row.get(col)
        if pd.notna(cell) and str(cell) == record.number:
            matched_field = col
            break

    if matched_field is None:
        return {"status": "miss", "matched_field": None, "winnings": 0.0}

    unit = payout.get("ticket_unit", 80) or 80
    winnings = float(payout.get(record.category, 0.0)) * (record.price / unit)
    return {"status": "hit", "matched_field": matched_field, "winnings": winnings}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/stats/test_tickets.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lottery/stats/tickets.py tests/stats/test_tickets.py
git commit -m "feat: ticket win/loss evaluation with scaled winnings"
```

---

### Task 4: Spending summary + suggestion overlap

**Files:**
- Modify: `src/lottery/stats/tickets.py`
- Test: `tests/stats/test_tickets.py`

**Interfaces:**
- Consumes: `evaluate_ticket` (Task 3); `suggest.suggest_all(...)` output `dict[str, pd.DataFrame]` whose category frames have a `value` column (Task 6 of prior sub-project, already in repo).
- Produces:
  - `suggestion_overlap(number: str, category: str, suggestions: dict[str, pd.DataFrame]) -> bool | None`.
  - `spending_summary(records: list, evaluations: list[dict]) -> dict` with keys `total_spent`, `total_winnings`, `net`, `by_category` (`{cat: {"spent": float, "winnings": float}}`). `records[i]` aligns with `evaluations[i]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/stats/test_tickets.py`:

```python
def test_suggestion_overlap_aligns_categories():
    suggestions = {
        "last2": pd.DataFrame({"value": ["23", "45"]}),
        "firstprize_last3": pd.DataFrame({"value": ["233"]}),
    }
    assert T.suggestion_overlap("23", "Last2", suggestions) is True
    assert T.suggestion_overlap("99", "Last2", suggestions) is False
    # FirstPrize compares the last 3 digits against firstprize_last3
    assert T.suggestion_overlap("112233", "FirstPrize", suggestions) is True
    # No table for category -> None
    assert T.suggestion_overlap("123", "Back3", suggestions) is None


def test_spending_summary_totals_and_net():
    recs = [
        TicketRecord.new(number="23", category="Last2", draw_date="2569-06-16", price=80.0),
        TicketRecord.new(number="99", category="Last2", draw_date="2569-06-16", price=80.0),
    ]
    evals = [
        {"status": "hit", "matched_field": "Last2", "winnings": 2000.0},
        {"status": "miss", "matched_field": None, "winnings": 0.0},
    ]
    summary = T.spending_summary(recs, evals)
    assert summary["total_spent"] == 160.0
    assert summary["total_winnings"] == 2000.0
    assert summary["net"] == 1840.0
    assert summary["by_category"]["Last2"]["spent"] == 160.0
    assert summary["by_category"]["Last2"]["winnings"] == 2000.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/stats/test_tickets.py -k "overlap or summary" -v`
Expected: FAIL (no attribute `suggestion_overlap`).

- [ ] **Step 3: Implement overlap + summary**

Append to `src/lottery/stats/tickets.py`:

```python
_SUGGEST_CATEGORY = {
    "Last2": "last2",
    "Back3": "back3",
    "Front3": "front3",
    "FirstPrize": "firstprize_last3",
}


def suggestion_overlap(number: str, category: str, suggestions: dict) -> bool | None:
    key = _SUGGEST_CATEGORY.get(category)
    table = suggestions.get(key) if key else None
    if table is None or table.empty or "value" not in table:
        return None
    needle = number[-3:] if category == "FirstPrize" else number
    values = {str(v) for v in table["value"].tolist()}
    return needle in values


def spending_summary(records: list, evaluations: list[dict]) -> dict:
    total_spent = 0.0
    total_winnings = 0.0
    by_category: dict[str, dict[str, float]] = {}
    for rec, ev in zip(records, evaluations):
        total_spent += rec.price
        total_winnings += ev["winnings"]
        bucket = by_category.setdefault(rec.category, {"spent": 0.0, "winnings": 0.0})
        bucket["spent"] += rec.price
        bucket["winnings"] += ev["winnings"]
    return {
        "total_spent": total_spent,
        "total_winnings": total_winnings,
        "net": total_winnings - total_spent,
        "by_category": by_category,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/stats/test_tickets.py -v`
Expected: PASS (7 tests total).

- [ ] **Step 5: Commit**

```bash
git add src/lottery/stats/tickets.py tests/stats/test_tickets.py
git commit -m "feat: ticket spending summary + suggestion overlap"
```

---

### Task 5: Chart + serialization helpers

**Files:**
- Create: `src/lottery/web/__init__.py` (empty for now)
- Create: `src/lottery/web/charts.py`
- Create: `src/lottery/web/serialize.py`
- Test: `tests/web/__init__.py`, `tests/web/test_serialize.py`

**Interfaces:**
- Produces:
  - `serialize.figure_json(fig) -> dict` — JSON-safe dict with `data`/`layout` keys (via `plotly.io.to_json`).
  - `serialize.frame_records(df: pd.DataFrame) -> list[dict]` — JSON-safe records (NA → null) via `df.to_json(orient="records")`.
  - `charts.frequency_bar(freq, title) -> dict`, `charts.heatmap_10x10(freq, title) -> dict`, `charts.transition_heatmap(matrix, title) -> dict`, `charts.suggestion_bar(df, title) -> dict` — each returns a `figure_json` dict.

- [ ] **Step 1: Write the failing test**

Create `tests/web/__init__.py` (empty) and `tests/web/test_serialize.py`:

```python
import pandas as pd

from lottery.web import serialize, charts


def test_frame_records_na_becomes_null():
    df = pd.DataFrame({"a": pd.array(["x", pd.NA], dtype="string"), "b": [1, 2]})
    recs = serialize.frame_records(df)
    assert recs == [{"a": "x", "b": 1}, {"a": None, "b": 2}]


def test_frequency_bar_returns_plotly_dict():
    freq = pd.DataFrame({"value": ["00", "01"], "count": [3, 5]})
    fig = charts.frequency_bar(freq, "t")
    assert "data" in fig and "layout" in fig
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/web/test_serialize.py -v`
Expected: FAIL (ModuleNotFoundError: lottery.web).

- [ ] **Step 3: Implement helpers**

Create `src/lottery/web/__init__.py` (empty — the factory is added in Task 6).

Create `src/lottery/web/serialize.py`:

```python
from __future__ import annotations

import json

import pandas as pd
import plotly.io as pio


def figure_json(fig) -> dict:
    return json.loads(pio.to_json(fig))


def frame_records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records"))
```

Create `src/lottery/web/charts.py`:

```python
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from lottery.web.serialize import figure_json


def frequency_bar(freq: pd.DataFrame, title: str) -> dict:
    return figure_json(px.bar(freq, x="value", y="count", title=title))


def heatmap_10x10(freq: pd.DataFrame, title: str) -> dict:
    grid = [[0] * 10 for _ in range(10)]
    for _, row in freq.iterrows():
        value = str(row["value"]).zfill(2)
        grid[int(value[0])][int(value[1])] = row["count"]
    fig = go.Figure(
        data=go.Heatmap(z=grid, x=list(range(10)), y=list(range(10))),
        layout=go.Layout(title=title),
    )
    return figure_json(fig)


def transition_heatmap(matrix: pd.DataFrame, title: str) -> dict:
    fig = go.Figure(
        data=go.Heatmap(z=matrix.to_numpy(), x=list(matrix.columns), y=list(matrix.index)),
        layout=go.Layout(title=title),
    )
    return figure_json(fig)


def suggestion_bar(df: pd.DataFrame, title: str) -> dict:
    return figure_json(px.bar(df, x="value", y="score", title=title))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/web/test_serialize.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lottery/web/__init__.py src/lottery/web/charts.py src/lottery/web/serialize.py tests/web
git commit -m "feat: web chart + serialization helpers (plotly dicts)"
```

---

### Task 6: App factory + memoized data state

**Files:**
- Modify: `src/lottery/web/__init__.py`
- Create: `src/lottery/web/state.py`
- Create: `src/lottery/web/templates/base.html`
- Create: `src/lottery/web/static/css/style.css`
- Test: `tests/web/test_app.py`

**Interfaces:**
- Consumes: `load_config` (`config.py`), `DrawRepository` (`data/repository.py`), `add_features` (`features/engineering.py`).
- Produces:
  - `state.AppState` holding a cached features DataFrame: `get_frame() -> pd.DataFrame` (memoized), `clear() -> None`.
  - `web.create_app(config_path: Path | None = None) -> Flask` factory. Registers blueprints in later tasks; for now exposes `GET /health` → `{"status": "ok"}` and attaches `app.config["LOTTERY"]` = `{"cfg", "state"}`.

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_app.py`:

```python
from lottery.web import create_app


def _client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_health_ok():
    resp = _client().get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/web/test_app.py -v`
Expected: FAIL (ImportError: cannot import name `create_app`).

- [ ] **Step 3: Implement state**

Create `src/lottery/web/state.py`:

```python
from __future__ import annotations

import pandas as pd

from lottery.config import Config
from lottery.data.repository import DrawRepository
from lottery.features.engineering import add_features


class AppState:
    """Lazily loads and memoizes the feature-engineered draws DataFrame."""

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._frame: pd.DataFrame | None = None

    def get_frame(self) -> pd.DataFrame:
        if self._frame is None:
            repo = DrawRepository(self._cfg.db_path, self._cfg.csv_path)
            self._frame = add_features(repo.load())
        return self._frame

    def clear(self) -> None:
        self._frame = None
```

- [ ] **Step 4: Implement factory**

Replace `src/lottery/web/__init__.py` with:

```python
from __future__ import annotations

from pathlib import Path

from flask import Flask

from lottery.config import load_config
from lottery.web.state import AppState


def create_app(config_path: Path | None = None) -> Flask:
    app = Flask(__name__)
    cfg = load_config(config_path)
    app.config["LOTTERY"] = {"cfg": cfg, "state": AppState(cfg)}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    from lottery.web.blueprints.analysis import bp as analysis_bp
    from lottery.web.blueprints.tickets import bp as tickets_bp

    app.register_blueprint(analysis_bp)
    app.register_blueprint(tickets_bp)
    return app
```

NOTE: the two blueprint imports will fail until Tasks 7 and 9 create them. To keep this task runnable on its own, **temporarily comment out the two `register_blueprint` lines and their imports**, then re-enable each as its blueprint lands. (Task 7 re-enables `analysis_bp`; Task 9 re-enables `tickets_bp`.)

- [ ] **Step 5: Create base template + css**

Create `src/lottery/web/templates/base.html`:

```html
<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}สถิติหวย{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
</head>
<body>
  <nav class="nav">
    <a href="{{ url_for('analysis.page') }}">📊 วิเคราะห์สถิติ</a>
    <a href="{{ url_for('tickets.page') }}">🎫 ตั๋วของฉัน</a>
  </nav>
  <div class="disclaimer">{{ disclaimer }}</div>
  <main>{% block content %}{% endblock %}</main>
  {% block scripts %}{% endblock %}
</body>
</html>
```

NOTE: `url_for('analysis.page')` / `url_for('tickets.page')` resolve once Tasks 7/9 land. While those blueprints are commented out in Step 4, this template is not rendered by any route yet, so `test_health_ok` is unaffected.

Create `src/lottery/web/static/css/style.css`:

```css
body { font-family: system-ui, sans-serif; margin: 0; color: #222; }
.nav { display: flex; gap: 1rem; padding: 0.75rem 1rem; background: #1f2937; }
.nav a { color: #fff; text-decoration: none; font-weight: 600; }
.disclaimer { background: #fef3c7; padding: 0.6rem 1rem; font-size: 0.9rem; }
main { padding: 1rem; }
.tabs { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem; }
.tabs button { padding: 0.4rem 0.8rem; cursor: pointer; }
.tabs button.active { background: #1f2937; color: #fff; }
table { border-collapse: collapse; margin: 0.5rem 0; }
th, td { border: 1px solid #ddd; padding: 0.3rem 0.6rem; text-align: left; }
.card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 0.5rem 0; display: inline-block; }
.hit { color: #047857; font-weight: 700; }
.miss { color: #b91c1c; }
form.ticket-form { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: end; margin-bottom: 1rem; }
form.ticket-form label { display: flex; flex-direction: column; font-size: 0.85rem; }
</style>
```

(Remove the trailing `</style>` — it is CSS, not HTML; end the file after the last rule.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/web/test_app.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/lottery/web tests/web/test_app.py
git commit -m "feat: Flask app factory + memoized data state + base template"
```

---

### Task 7: Analysis blueprint — page, overview, frequency, gap, update

**Files:**
- Create: `src/lottery/web/blueprints/__init__.py`
- Create: `src/lottery/web/blueprints/analysis.py`
- Create: `src/lottery/web/templates/analysis.html`
- Modify: `src/lottery/web/__init__.py` (re-enable analysis blueprint registration)
- Test: `tests/web/test_analysis.py`

**Interfaces:**
- Consumes: `AppState.get_frame()`; stats modules `frequency`, `summary`; `web.charts`, `web.serialize`; `update_dataset`, `UpdateError`, `DrawRepository`.
- Produces blueprint `bp = Blueprint("analysis", ...)` with routes:
  - `GET /` → `page()` renders `analysis.html`.
  - `GET /api/analysis/overview?target=&year_from=&year_to=` → metrics + recent rows.
  - `GET /api/analysis/frequency?target=&year_from=&year_to=&window=` → `{figure, heatmap, hot, cold}`.
  - `GET /api/analysis/gap?target=&year_from=&year_to=` → `{table}`.
  - `POST /api/update` → `{added, latest_before, latest_after, message}` or `{error}`.
- Helper `_view(state, args) -> (df_view, series, target)` shared by endpoints, applying year filter + target dropna.

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_analysis.py`:

```python
from lottery.web import create_app


def _client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_page_renders_with_disclaimer():
    resp = _client().get("/")
    assert resp.status_code == 200
    assert "หวยเป็นการสุ่ม" in resp.get_data(as_text=True)


def test_overview_returns_metrics():
    resp = _client().get("/api/analysis/overview?target=Last2")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "draw_count" in body
    assert "entropy" in body


def test_frequency_returns_figure():
    resp = _client().get("/api/analysis/frequency?target=Last2")
    body = resp.get_json()
    assert "data" in body["figure"]
    assert isinstance(body["hot"], list)


def test_gap_returns_table():
    resp = _client().get("/api/analysis/gap?target=Last2")
    assert isinstance(resp.get_json()["table"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/web/test_analysis.py -v`
Expected: FAIL (404 on `/`, blueprint not registered).

- [ ] **Step 3: Implement the blueprint**

Create `src/lottery/web/blueprints/__init__.py` (empty).

Create `src/lottery/web/blueprints/analysis.py`:

```python
from __future__ import annotations

from flask import Blueprint, current_app, render_template, request

from lottery.data.repository import DrawRepository
from lottery.data.updater import UpdateError, update_dataset
from lottery.stats import frequency, summary
from lottery.stats.suggest import DISCLAIMER
from lottery.web import charts, serialize

bp = Blueprint("analysis", __name__)

TARGETS = ["Last2", "Front3_1", "Back3_1", "FirstPrize"]


def _ctx():
    return current_app.config["LOTTERY"]


def _view(args):
    df = _ctx()["state"].get_frame()
    target = args.get("target", "Last2")
    years = sorted(df["Year"].unique())
    year_from = int(args.get("year_from", years[0]))
    year_to = int(args.get("year_to", years[-1]))
    mask = (df["Year"] >= year_from) & (df["Year"] <= year_to)
    view = df[mask]
    series = view[target].dropna() if target in view else view.iloc[0:0]
    return view, series, target


@bp.get("/")
def page():
    return render_template("analysis.html", disclaimer=DISCLAIMER, targets=TARGETS)


@bp.get("/api/analysis/overview")
def overview():
    view, series, target = _view(request.args)
    counts = frequency.frequency(series).set_index("value")["count"] if not series.empty else None
    body = {
        "draw_count": int(len(view)),
        "date_range": [str(view.iloc[0]["DrawDate"]), str(view.iloc[-1]["DrawDate"])]
        if not view.empty
        else [None, None],
        "entropy": float(summary.shannon_entropy(counts)) if counts is not None else None,
        "recent": serialize.frame_records(view.tail(20)),
    }
    if target == "Last2" and counts is not None:
        _, p = summary.chi_square_uniform(counts, 100)
        body["chi_square_p"] = float(p)
    return body


@bp.get("/api/analysis/frequency")
def frequency_endpoint():
    view, series, target = _view(request.args)
    window = int(request.args.get("window", 0))
    if series.empty:
        return {"figure": {}, "heatmap": None, "hot": [], "cold": []}
    freq = frequency.frequency(series)
    hot_series = series.tail(window) if window else series
    hot, cold = frequency.hot_cold(hot_series)
    body = {
        "figure": charts.frequency_bar(freq, f"ความถี่ {target}"),
        "heatmap": charts.heatmap_10x10(freq, "ความถี่ 00–99") if target == "Last2" else None,
        "hot": serialize.frame_records(hot),
        "cold": serialize.frame_records(cold),
    }
    return body


@bp.get("/api/analysis/gap")
def gap():
    _, series, _ = _view(request.args)
    table = serialize.frame_records(frequency.current_gap(series))
    return {"table": table}


@bp.post("/api/update")
def update():
    cfg = _ctx()["cfg"]
    repo = DrawRepository(cfg.db_path, cfg.csv_path)
    try:
        report = update_dataset(repo)
    except UpdateError as exc:
        return {"error": str(exc)}, 502
    _ctx()["state"].clear()
    msg = (
        f"เพิ่ม {report.added} งวด ({report.latest_before} → {report.latest_after})"
        if report.added
        else "ข้อมูลเป็นปัจจุบันแล้ว"
    )
    return {
        "added": report.added,
        "latest_before": report.latest_before,
        "latest_after": report.latest_after,
        "message": msg,
    }
```

- [ ] **Step 4: Create the page template**

Create `src/lottery/web/templates/analysis.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>📊 วิเคราะห์สถิติหวยย้อนหลัง (พ.ศ. 2533–2569)</h1>
<div class="controls">
  <label>ประเภทเลข
    <select id="target">
      {% for t in targets %}<option value="{{ t }}">{{ t }}</option>{% endfor %}
    </select>
  </label>
  <label>Hot/Cold N งวดล่าสุด (0=ทั้งหมด)
    <input id="window" type="number" value="0" min="0" step="10">
  </label>
  <button id="refresh">🔄 อัปเดตข้อมูลล่าสุด</button>
  <span id="update-status"></span>
</div>
<div class="tabs" id="tabs">
  <button data-tab="overview" class="active">ภาพรวม</button>
  <button data-tab="frequency">ความถี่</button>
  <button data-tab="gap">ช่วงห่าง</button>
  <button data-tab="digits">หลักตัวเลข</button>
  <button data-tab="pairs">คู่/สามตัว</button>
  <button data-tab="trend">แนวโน้ม</button>
  <button data-tab="suggestions">ตัวเลขน่าสนใจ</button>
</div>
<div id="panel"></div>
{% endblock %}
{% block scripts %}
<script src="{{ url_for('static', filename='js/charts.js') }}"></script>
<script src="{{ url_for('static', filename='js/analysis.js') }}"></script>
{% endblock %}
```

- [ ] **Step 5: Re-enable analysis blueprint**

In `src/lottery/web/__init__.py`, ensure the analysis import + `app.register_blueprint(analysis_bp)` lines are active (uncomment from Task 6). Leave `tickets_bp` commented until Task 9.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/web/test_analysis.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add src/lottery/web tests/web/test_analysis.py
git commit -m "feat: analysis blueprint (overview/frequency/gap/update) + page"
```

---

### Task 8: Analysis blueprint — digits, pairs, trend, suggestions

**Files:**
- Modify: `src/lottery/web/blueprints/analysis.py`
- Test: `tests/web/test_analysis.py`

**Interfaces:**
- Consumes: stats modules `digits`, `pairs`, `sequence`, `suggest`; `web.charts.transition_heatmap`, `charts.suggestion_bar`.
- Produces routes:
  - `GET /api/analysis/digits?target=&year_from=&year_to=` → `{position_heatmap, odd_even, high_low}`.
  - `GET /api/analysis/pairs?...` → `{pairs, triples}`.
  - `GET /api/analysis/trend?...` → `{markov, yearly, monthly}`.
  - `GET /api/analysis/suggestions` → `{categories: {cat: {figure, table}}, firstprize_digits, disclaimer}`.

- [ ] **Step 1: Write the failing test**

Append to `tests/web/test_analysis.py`:

```python
def test_digits_endpoint():
    resp = _client().get("/api/analysis/digits?target=Last2")
    body = resp.get_json()
    assert "data" in body["position_heatmap"]
    assert isinstance(body["odd_even"], list)


def test_pairs_endpoint():
    body = _client().get("/api/analysis/pairs?target=Last2").get_json()
    assert isinstance(body["pairs"], list)
    assert isinstance(body["triples"], list)


def test_trend_endpoint():
    body = _client().get("/api/analysis/trend?target=Last2").get_json()
    assert "data" in body["markov"]
    assert isinstance(body["yearly"], list)


def test_suggestions_endpoint():
    body = _client().get("/api/analysis/suggestions").get_json()
    assert "last2" in body["categories"]
    assert "หวยเป็นการสุ่ม" in body["disclaimer"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/web/test_analysis.py -k "digits or pairs or trend or suggestions" -v`
Expected: FAIL (404).

- [ ] **Step 3: Implement the endpoints**

Add imports at the top of `analysis.py`:

```python
from lottery.stats import digits, pairs, sequence, suggest
```

Append routes to `analysis.py`:

```python
@bp.get("/api/analysis/digits")
def digits_endpoint():
    _, series, _ = _view(request.args)
    if series.empty:
        return {"position_heatmap": {}, "odd_even": [], "high_low": []}
    return {
        "position_heatmap": charts.transition_heatmap(
            digits.position_distribution(series).T, "การกระจายตัวตามตำแหน่งหลัก"
        ),
        "odd_even": serialize.frame_records(digits.odd_even_ratio(series)),
        "high_low": serialize.frame_records(digits.high_low_ratio(series)),
    }


@bp.get("/api/analysis/pairs")
def pairs_endpoint():
    _, series, _ = _view(request.args)
    return {
        "pairs": serialize.frame_records(pairs.digit_pair_frequency(series).head(20)),
        "triples": serialize.frame_records(pairs.digit_triple_frequency(series).head(20)),
    }


@bp.get("/api/analysis/trend")
def trend_endpoint():
    view, series, _ = _view(request.args)
    yearly = view.groupby("Year").size().rename("draws").reset_index()
    monthly = view.groupby("Month").size().rename("draws").reset_index()
    markov = (
        charts.transition_heatmap(sequence.markov_transition(series), "Markov Transition")
        if not series.empty
        else {}
    )
    return {
        "markov": markov,
        "yearly": serialize.frame_records(yearly),
        "monthly": serialize.frame_records(monthly),
    }


@bp.get("/api/analysis/suggestions")
def suggestions_endpoint():
    cfg = _ctx()["cfg"]
    df = _ctx()["state"].get_frame()
    results = suggest.suggest_all(
        df, weights=cfg.weights, recent_window=cfg.recent_window, top_n=cfg.top_n
    )
    labels = {
        "last2": "เลขท้าย 2 ตัว",
        "back3": "เลขท้าย 3 ตัว",
        "front3": "เลขหน้า 3 ตัว",
        "firstprize_last3": "3 ตัวท้ายรางวัลที่ 1",
    }
    categories = {}
    for cat, label in labels.items():
        cand = results[cat]
        categories[cat] = {
            "label": label,
            "figure": charts.suggestion_bar(cand, f"คะแนนเชิงสถิติ {label}") if not cand.empty else {},
            "table": serialize.frame_records(cand),
        }
    return {
        "categories": categories,
        "firstprize_digits": serialize.frame_records(results["firstprize_digits"]),
        "disclaimer": suggest.DISCLAIMER,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/web/test_analysis.py -v`
Expected: PASS (8 tests total).

- [ ] **Step 5: Commit**

```bash
git add src/lottery/web/blueprints/analysis.py tests/web/test_analysis.py
git commit -m "feat: analysis endpoints for digits/pairs/trend/suggestions"
```

---

### Task 9: Tickets blueprint

**Files:**
- Create: `src/lottery/web/blueprints/tickets.py`
- Create: `src/lottery/web/templates/tickets.html`
- Modify: `src/lottery/web/__init__.py` (re-enable tickets blueprint)
- Test: `tests/web/test_tickets_api.py`

**Interfaces:**
- Consumes: `tickets.store`, `TicketRecord`, `stats.tickets` (evaluate/summary/overlap), `suggest.suggest_all`, `AppState.get_frame`, `cfg.tickets_path`, `cfg.payout`.
- Produces blueprint `bp = Blueprint("tickets", ...)`:
  - `GET /tickets` → `page()` renders `tickets.html`.
  - `GET /api/draw-dates` → `{dates: [...]}` (dataset DrawDates, newest first).
  - `GET /api/tickets` → `{tickets: [ {record fields..., status, matched_field, winnings, overlap} ]}`.
  - `POST /api/tickets` (JSON `{number, category, draw_date, price}`) → created enriched ticket, 201; `{error}` 400 on invalid.
  - `DELETE /api/tickets/<id>` → `{deleted: true}` 200 / `{error}` 404.
  - `GET /api/tickets/summary` → spending summary dict.

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_tickets_api.py`:

```python
from lottery.web import create_app


def _client(tmp_path):
    app = create_app()
    app.config.update(TESTING=True)
    # redirect tickets file to a temp path (Config is a frozen dataclass; rebuild it)
    app.config["LOTTERY"]["cfg"] = app.config["LOTTERY"]["cfg"].__class__(
        **{**app.config["LOTTERY"]["cfg"].__dict__, "tickets_path": tmp_path / "t.json"}
    )
    return app.test_client(), app


def test_draw_dates_listed(tmp_path):
    client, _ = _client(tmp_path)
    body = client.get("/api/draw-dates").get_json()
    assert isinstance(body["dates"], list) and body["dates"]


def test_post_list_delete_ticket(tmp_path):
    client, app = _client(tmp_path)
    date = client.get("/api/draw-dates").get_json()["dates"][0]
    resp = client.post("/api/tickets", json={"number": "23", "category": "Last2", "draw_date": date, "price": 80})
    assert resp.status_code == 201
    tid = resp.get_json()["id"]
    listed = client.get("/api/tickets").get_json()["tickets"]
    assert any(t["id"] == tid for t in listed)
    assert "status" in listed[0]
    assert client.delete(f"/api/tickets/{tid}").status_code == 200


def test_post_rejects_unknown_draw_date(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.post("/api/tickets", json={"number": "23", "category": "Last2", "draw_date": "0000-00-00", "price": 80})
    assert resp.status_code == 400


def test_post_rejects_bad_category(tmp_path):
    client, _ = _client(tmp_path)
    date = client.get("/api/draw-dates").get_json()["dates"][0]
    resp = client.post("/api/tickets", json={"number": "23", "category": "Nope", "draw_date": date, "price": 80})
    assert resp.status_code == 400
```

NOTE: `Config` is a frozen dataclass; the test rebuilds it via `__class__(**{...})` to point `tickets_path` at a temp file. This relies on every `Config` field being a constructor arg (true as of Task 1).

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/web/test_tickets_api.py -v`
Expected: FAIL (404 / blueprint missing).

- [ ] **Step 3: Implement the blueprint**

Create `src/lottery/web/blueprints/tickets.py`:

```python
from __future__ import annotations

from flask import Blueprint, current_app, render_template, request

from lottery.stats import tickets as ticket_stats
from lottery.stats import suggest
from lottery.stats.suggest import DISCLAIMER
from lottery.tickets import store
from lottery.tickets.models import CATEGORIES, TicketRecord

bp = Blueprint("tickets", __name__)


def _ctx():
    return current_app.config["LOTTERY"]


def _enrich(records):
    cfg = _ctx()["cfg"]
    df = _ctx()["state"].get_frame()
    suggestions = suggest.suggest_all(
        df, weights=cfg.weights, recent_window=cfg.recent_window, top_n=cfg.top_n
    )
    out = []
    evals = []
    for rec in records:
        ev = ticket_stats.evaluate_ticket(rec, df, cfg.payout)
        evals.append(ev)
        out.append(
            {
                **rec.to_dict(),
                "status": ev["status"],
                "matched_field": ev["matched_field"],
                "winnings": ev["winnings"],
                "overlap": ticket_stats.suggestion_overlap(rec.number, rec.category, suggestions),
            }
        )
    return out, evals


@bp.get("/tickets")
def page():
    return render_template("tickets.html", disclaimer=DISCLAIMER, categories=list(CATEGORIES))


@bp.get("/api/draw-dates")
def draw_dates():
    df = _ctx()["state"].get_frame()
    dates = [str(d) for d in df["DrawDate"].tolist()][::-1]
    return {"dates": dates}


@bp.get("/api/tickets")
def list_tickets():
    cfg = _ctx()["cfg"]
    records = store.load(cfg.tickets_path)
    enriched, _ = _enrich(records)
    return {"tickets": enriched}


@bp.post("/api/tickets")
def create_ticket():
    cfg = _ctx()["cfg"]
    data = request.get_json(silent=True) or {}
    number = str(data.get("number", "")).strip()
    category = data.get("category")
    draw_date = data.get("draw_date")
    if not number:
        return {"error": "number is required"}, 400
    if category not in CATEGORIES:
        return {"error": "invalid category"}, 400
    try:
        price = float(data.get("price"))
    except (TypeError, ValueError):
        return {"error": "invalid price"}, 400
    if price <= 0:
        return {"error": "price must be positive"}, 400
    df = _ctx()["state"].get_frame()
    if draw_date not in set(df["DrawDate"].astype(str)):
        return {"error": "unknown draw_date"}, 400
    rec = TicketRecord.new(number=number, category=category, draw_date=draw_date, price=price)
    store.add(cfg.tickets_path, rec)
    enriched, _ = _enrich([rec])
    return enriched[0], 201


@bp.delete("/api/tickets/<ticket_id>")
def remove_ticket(ticket_id: str):
    cfg = _ctx()["cfg"]
    if store.delete(cfg.tickets_path, ticket_id):
        return {"deleted": True}
    return {"error": "not found"}, 404


@bp.get("/api/tickets/summary")
def summary():
    cfg = _ctx()["cfg"]
    records = store.load(cfg.tickets_path)
    _, evals = _enrich(records)
    return ticket_stats.spending_summary(records, evals)
```

- [ ] **Step 4: Create the tickets template**

Create `src/lottery/web/templates/tickets.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>🎫 ตั๋วของฉัน</h1>
<form class="ticket-form" id="ticket-form">
  <label>เลข<input id="t-number" required></label>
  <label>ประเภท
    <select id="t-category">
      {% for c in categories %}<option value="{{ c }}">{{ c }}</option>{% endfor %}
    </select>
  </label>
  <label>งวด<select id="t-draw"></select></label>
  <label>ราคา (บาท)<input id="t-price" type="number" value="80" min="1" step="1"></label>
  <button type="submit">บันทึก</button>
</form>
<div id="summary" class="card"></div>
<div id="ticket-list"></div>
{% endblock %}
{% block scripts %}
<script src="{{ url_for('static', filename='js/tickets.js') }}"></script>
{% endblock %}
```

- [ ] **Step 5: Re-enable tickets blueprint**

In `src/lottery/web/__init__.py`, uncomment the `tickets_bp` import and `app.register_blueprint(tickets_bp)`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/web/test_tickets_api.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add src/lottery/web tests/web/test_tickets_api.py
git commit -m "feat: tickets blueprint (CRUD + summary + draw-dates)"
```

---

### Task 10: Frontend JavaScript (charts, analysis tabs, tickets)

**Files:**
- Create: `src/lottery/web/static/js/charts.js`
- Create: `src/lottery/web/static/js/analysis.js`
- Create: `src/lottery/web/static/js/tickets.js`
- Test: `tests/web/test_static.py`

**Interfaces:**
- Consumes: the JSON API from Tasks 7–9; global `Plotly` from CDN.
- Produces: browser behavior. Tested only at the smoke level (files served, referenced by pages).

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_static.py`:

```python
from lottery.web import create_app


def _client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_js_assets_served():
    client = _client()
    for name in ("charts.js", "analysis.js", "tickets.js"):
        resp = client.get(f"/static/js/{name}")
        assert resp.status_code == 200, name


def test_pages_reference_scripts():
    html = _client().get("/").get_data(as_text=True)
    assert "analysis.js" in html
    tickets = _client().get("/tickets").get_data(as_text=True)
    assert "tickets.js" in tickets
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/web/test_static.py -v`
Expected: FAIL (404 on the JS assets).

- [ ] **Step 3: Implement charts.js**

Create `src/lottery/web/static/js/charts.js`:

```javascript
async function getJSON(url, opts) {
  const resp = await fetch(url, opts);
  return resp.json();
}

function renderFigure(elId, figure) {
  const el = document.getElementById(elId);
  if (!el) return;
  if (!figure || !figure.data) { el.innerHTML = "<p>ไม่มีข้อมูล</p>"; return; }
  Plotly.newPlot(el, figure.data, figure.layout || {}, { responsive: true });
}

function renderTable(rows) {
  if (!rows || !rows.length) return "<p>ไม่มีข้อมูล</p>";
  const cols = Object.keys(rows[0]);
  const head = cols.map((c) => `<th>${c}</th>`).join("");
  const body = rows
    .map((r) => `<tr>${cols.map((c) => `<td>${r[c] ?? ""}</td>`).join("")}</tr>`)
    .join("");
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}
```

- [ ] **Step 4: Implement analysis.js**

Create `src/lottery/web/static/js/analysis.js`:

```javascript
const panel = document.getElementById("panel");
const targetEl = document.getElementById("target");
const windowEl = document.getElementById("window");
let activeTab = "overview";

function qs() {
  return `target=${encodeURIComponent(targetEl.value)}&window=${encodeURIComponent(windowEl.value)}`;
}

const renderers = {
  async overview() {
    const d = await getJSON(`/api/analysis/overview?${qs()}`);
    panel.innerHTML =
      `<div class="card">จำนวนงวด: ${d.draw_count}</div>` +
      `<div class="card">ช่วงวันที่: ${d.date_range[0]} → ${d.date_range[1]}</div>` +
      `<div class="card">Entropy: ${d.entropy != null ? d.entropy.toFixed(3) : "-"}</div>` +
      (d.chi_square_p != null ? `<div class="card">χ² p-value: ${d.chi_square_p.toFixed(3)}</div>` : "") +
      renderTable(d.recent);
  },
  async frequency() {
    const d = await getJSON(`/api/analysis/frequency?${qs()}`);
    panel.innerHTML =
      `<div id="freq-fig"></div>` +
      (d.heatmap ? `<div id="freq-heat"></div>` : "") +
      `<h3>เลขมาบ่อย (Hot)</h3>${renderTable(d.hot)}` +
      `<h3>เลขมาน้อย (Cold)</h3>${renderTable(d.cold)}`;
    renderFigure("freq-fig", d.figure);
    if (d.heatmap) renderFigure("freq-heat", d.heatmap);
  },
  async gap() {
    const d = await getJSON(`/api/analysis/gap?${qs()}`);
    panel.innerHTML = `<h3>ช่วงห่างตั้งแต่ออกครั้งล่าสุด</h3>${renderTable(d.table)}`;
  },
  async digits() {
    const d = await getJSON(`/api/analysis/digits?${qs()}`);
    panel.innerHTML = `<div id="pos-fig"></div><h3>คี่/คู่</h3>${renderTable(d.odd_even)}<h3>สูง/ต่ำ</h3>${renderTable(d.high_low)}`;
    renderFigure("pos-fig", d.position_heatmap);
  },
  async pairs() {
    const d = await getJSON(`/api/analysis/pairs?${qs()}`);
    panel.innerHTML = `<h3>คู่ตัวเลข</h3>${renderTable(d.pairs)}<h3>สามตัวเลข</h3>${renderTable(d.triples)}`;
  },
  async trend() {
    const d = await getJSON(`/api/analysis/trend?${qs()}`);
    panel.innerHTML = `<div id="markov-fig"></div><h3>จำนวนงวดต่อปี</h3>${renderTable(d.yearly)}<h3>จำนวนงวดต่อเดือน</h3>${renderTable(d.monthly)}`;
    renderFigure("markov-fig", d.markov);
  },
  async suggestions() {
    const d = await getJSON(`/api/analysis/suggestions`);
    let html = `<div class="disclaimer">${d.disclaimer}</div>`;
    for (const cat of Object.keys(d.categories)) {
      const c = d.categories[cat];
      html += `<h3>${c.label}</h3><div id="sug-${cat}"></div>${renderTable(c.table)}`;
    }
    html += `<h3>ความถี่ตัวเลขแต่ละหลัก (รางวัลที่ 1)</h3>${renderTable(d.firstprize_digits)}`;
    panel.innerHTML = html;
    for (const cat of Object.keys(d.categories)) renderFigure(`sug-${cat}`, d.categories[cat].figure);
  },
};

function activate(tab) {
  activeTab = tab;
  document.querySelectorAll("#tabs button").forEach((b) =>
    b.classList.toggle("active", b.dataset.tab === tab)
  );
  renderers[tab]();
}

document.getElementById("tabs").addEventListener("click", (e) => {
  if (e.target.dataset.tab) activate(e.target.dataset.tab);
});
targetEl.addEventListener("change", () => renderers[activeTab]());
windowEl.addEventListener("change", () => renderers[activeTab]());

document.getElementById("refresh").addEventListener("click", async () => {
  const status = document.getElementById("update-status");
  status.textContent = "กำลังดึงข้อมูล...";
  const resp = await fetch("/api/update", { method: "POST" });
  const d = await resp.json();
  status.textContent = d.message || d.error || "";
  renderers[activeTab]();
});

activate("overview");
```

- [ ] **Step 5: Implement tickets.js**

Create `src/lottery/web/static/js/tickets.js`:

```javascript
async function loadDraws() {
  const d = await getJSON("/api/draw-dates");
  const sel = document.getElementById("t-draw");
  sel.innerHTML = d.dates.map((x) => `<option value="${x}">${x}</option>`).join("");
}

async function loadSummary() {
  const s = await getJSON("/api/tickets/summary");
  const card = document.getElementById("summary");
  card.innerHTML =
    `รวมจ่าย: ${s.total_spent ?? 0} บาท | รวมถูกรางวัล: ${s.total_winnings ?? 0} บาท | สุทธิ: ${s.net ?? 0} บาท`;
}

async function loadTickets() {
  const d = await getJSON("/api/tickets");
  const rows = d.tickets
    .map(
      (t) =>
        `<tr><td>${t.number}</td><td>${t.category}</td><td>${t.draw_date}</td><td>${t.price}</td>` +
        `<td class="${t.status === "hit" ? "hit" : "miss"}">${t.status}</td>` +
        `<td>${t.matched_field ?? ""}</td><td>${t.winnings}</td>` +
        `<td>${t.overlap === null ? "-" : t.overlap ? "✔" : "✘"}</td>` +
        `<td><button data-del="${t.id}">ลบ</button></td></tr>`
    )
    .join("");
  document.getElementById("ticket-list").innerHTML =
    `<table><thead><tr><th>เลข</th><th>ประเภท</th><th>งวด</th><th>ราคา</th><th>ผล</th><th>ตรงกับ</th><th>เงินรางวัล</th><th>อยู่ในรายการแนะนำ</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;
  document.querySelectorAll("[data-del]").forEach((b) =>
    b.addEventListener("click", async () => {
      await fetch(`/api/tickets/${b.dataset.del}`, { method: "DELETE" });
      refresh();
    })
  );
}

async function refresh() {
  await loadTickets();
  await loadSummary();
}

document.getElementById("ticket-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    number: document.getElementById("t-number").value,
    category: document.getElementById("t-category").value,
    draw_date: document.getElementById("t-draw").value,
    price: document.getElementById("t-price").value,
  };
  const resp = await fetch("/api/tickets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const err = await resp.json();
    alert(err.error || "บันทึกไม่สำเร็จ");
    return;
  }
  document.getElementById("t-number").value = "";
  refresh();
});

loadDraws().then(refresh);
```

NOTE: `charts.js` defines `getJSON`/`renderTable`; `tickets.html` does not include it, so `tickets.js` uses its own `getJSON` — but `getJSON` is only defined in `charts.js`. Add `getJSON` locally to `tickets.js` to avoid the dependency: prepend
```javascript
async function getJSON(url) { return (await fetch(url)).json(); }
```
to `tickets.js`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/web/test_static.py -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add src/lottery/web/static/js tests/web/test_static.py
git commit -m "feat: frontend JS for analysis tabs + tickets page"
```

---

### Task 11: Remove Streamlit, wire CLI, update docs

**Files:**
- Delete: `src/lottery/dashboard/` (whole package)
- Delete: `tests/dashboard/test_charts.py` (and `tests/dashboard/` if empty)
- Modify: `pyproject.toml` (`[project.scripts]` add web entry)
- Modify: `src/lottery/cli.py` (optional `serve` subcommand)
- Modify: `CLAUDE.md` (run command + state)
- Test: full suite + ruff

**Interfaces:**
- Consumes: `web.create_app`.
- Produces: `cli` gains a `serve` subcommand running the Flask dev server. Streamlit fully removed.

- [ ] **Step 1: Delete the Streamlit dashboard and its test**

```bash
git rm -r src/lottery/dashboard tests/dashboard
```

- [ ] **Step 2: Add a serve subcommand (write test first)**

Add to `tests/test_cli.py`:

```python
def test_serve_builds_app(monkeypatch):
    import lottery.cli as cli

    called = {}

    def fake_run(self, *a, **k):
        called["ran"] = True

    monkeypatch.setattr("flask.Flask.run", fake_run)
    cli.main(["serve"])
    assert called["ran"]
```

- [ ] **Step 3: Run it to verify it fails**

Run: `.venv/bin/pytest tests/test_cli.py::test_serve_builds_app -v`
Expected: FAIL (unknown subcommand `serve`).

- [ ] **Step 4: Implement the subcommand**

In `src/lottery/cli.py`, register a `serve` subparser whose handler does:

```python
def _serve(args) -> int:
    from lottery.web import create_app

    create_app().run(host=args.host, port=args.port, debug=args.debug)
    return 0
```

Wire a subparser: `serve` with `--host` (default `127.0.0.1`), `--port` (default `5000`, int), `--debug` (store_true). Match the existing argparse structure in `cli.py` (inspect it and follow the same pattern used by `update`/`suggest`).

- [ ] **Step 5: Run the new test**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 6: Update pyproject scripts**

In `pyproject.toml`, confirm `streamlit` is gone from `dependencies` and `flask` is present (from Task 1). No new `[project.scripts]` line required (the `lottery` entry now exposes `serve`).

- [ ] **Step 7: Update CLAUDE.md**

In CLAUDE.md "Environment / how to run":
- Replace the Streamlit run line with:
  `Run the web app: PYTHONPATH=src .venv/bin/flask --app lottery.web run` (or `.venv/bin/lottery serve`).
- In the dependencies line, replace `streamlit 1.58` with `flask <version>`.
Add a history entry dated 2026-06-29 noting the Flask refactor + My Tickets feature replaced Streamlit.

- [ ] **Step 8: Full verification**

Run:
```bash
.venv/bin/ruff check src tests
.venv/bin/pytest -q
```
Expected: ruff clean; all tests pass (prior 52 minus removed dashboard test, plus the new web/tickets/stats tests). Confirm no remaining references to streamlit:
```bash
grep -rn "streamlit" src tests pyproject.toml || echo "no streamlit refs"
```
Expected: `no streamlit refs`.

- [ ] **Step 9: Manual smoke (optional but recommended)**

```bash
PYTHONPATH=src .venv/bin/flask --app lottery.web run
```
Visit `http://127.0.0.1:5000/` (7 tabs render, charts draw, refresh works) and `/tickets` (add a ticket, see win/loss + summary, delete). Confirm the DISCLAIMER shows on both pages.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor: remove Streamlit, add Flask serve CLI + docs"
```

---

## Self-Review notes

- **Spec coverage:** full-parity tabs (Tasks 7–8 + JS Task 10); Plotly.js via figure dicts (Tasks 5/10); ticket fields + JSON store (Tasks 1–2); win/loss + winnings via config payout (Tasks 1, 3); spending summary + overlap (Task 4); draw-date dropdown from dataset (Task 9); single git-ignored JSON file (Tasks 1–2); Streamlit removed (Task 11); DISCLAIMER on every page/suggestions/winnings (Tasks 6–10); error handling for bad input/update failure/missing file (Tasks 3, 7, 9, 2). All covered.
- **Type consistency:** `evaluate_ticket` returns `{status, matched_field, winnings}` used identically in Tasks 4, 9. `suggestion_overlap(number, category, suggestions)` signature consistent Tasks 4/9. `figure_json`/`frame_records` consistent Tasks 5/7/8/9. `TicketRecord.new(*, number, category, draw_date, price)` consistent Tasks 2/3/9.
- **Honesty rule:** DISCLAIMER (`suggest.DISCLAIMER`) is rendered in base template, suggestions endpoint/JS, and the tickets page near winnings/net.
