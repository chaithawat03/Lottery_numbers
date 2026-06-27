# Lottery Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data layer, reusable descriptive statistical engine, and Thai-labelled Streamlit dashboard for 872 historical Thai lottery draws.

**Architecture:** Layered package with one-way dependencies (`dashboard → stats → features → data`). `repository` is the only SQLite consumer; `features`/`stats` are pure functions over pandas DataFrames, fully unit-tested and reusable by later sub-projects. On-the-fly computation (dataset is tiny), cached in the dashboard with `st.cache_data`.

**Tech Stack:** Python 3.13+ (dev on 3.14), pandas, numpy, scipy, plotly, streamlit, pytest, ruff.

## Global Constraints

- Python `>=3.13`. Test imports resolve via `pythonpath = ["src"]` in pyproject.
- Number columns (`FirstPrize`, `Last2`, `Front3_1`, `Front3_2`, `Back3_1`, `Back3_2`, `Back3_3`, `Back3_4`) are **strings**; empty era cells are `pandas.NA`, never `0`.
- `Year`/`Month` are ints; `DrawDate` is a `YYYY-MM-DD` string in the **Buddhist Era** calendar.
- Dataset has exactly **872 rows**, span `2533-01-16`..`2569-06-16`.
- Dependency direction: only `data/repository.py` imports `sqlite3`; only `dashboard/` imports `streamlit`; `features`/`stats` import neither.
- Dashboard UI labels in **Thai**; a visible disclaimer must state the analysis is descriptive/experimental and the lottery is random. **No prediction or guarantee anywhere.**
- Every task ends with a commit. Run `pytest` from the project root.

---

### Task 1: Project scaffolding, config, logging

**Files:**
- Create: `pyproject.toml`
- Create: `config/config.toml`
- Create: `src/lottery/__init__.py` (empty)
- Create: `src/lottery/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config(db_path: Path, csv_path: Path, default_window: int, log_level: str)`; `load_config(path: Path | None = None) -> Config`; `setup_logging(level: str = "INFO") -> None`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "lottery-analysis"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "pandas>=2.2",
    "numpy>=1.26",
    "scipy>=1.13",
    "plotly>=5.22",
    "streamlit>=1.36",
]

[project.optional-dependencies]
dev = ["pytest>=8.2", "ruff>=0.5"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py313"
```

- [ ] **Step 2: Create `config/config.toml`**

```toml
[paths]
db_path = "dataset/lottery_results.sqlite"
csv_path = "dataset/lottery_results.csv"

[analysis]
default_window = 100

[logging]
level = "INFO"
```

- [ ] **Step 3: Create `src/lottery/__init__.py`** (empty file)

- [ ] **Step 4: Write the failing test** — `tests/test_config.py`

```python
from pathlib import Path

from lottery.config import load_config

CONFIG_BODY = (
    '[paths]\ndb_path="a.sqlite"\ncsv_path="a.csv"\n'
    '[analysis]\ndefault_window=50\n[logging]\nlevel="INFO"\n'
)


def test_load_config_defaults(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(CONFIG_BODY)
    cfg = load_config(cfg_file)
    assert cfg.default_window == 50
    assert cfg.db_path == Path("a.sqlite")


def test_load_config_env_override(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(CONFIG_BODY)
    monkeypatch.setenv("LOTTERY_DEFAULT_WINDOW", "7")
    cfg = load_config(cfg_file)
    assert cfg.default_window == 7
```

- [ ] **Step 5: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lottery.config'`

- [ ] **Step 6: Write `src/lottery/config.py`**

```python
from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config/config.toml")


@dataclass(frozen=True)
class Config:
    db_path: Path
    csv_path: Path
    default_window: int
    log_level: str


def load_config(path: Path | None = None) -> Config:
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(path, "rb") as handle:
        data = tomllib.load(handle)
    return Config(
        db_path=Path(os.getenv("LOTTERY_DB_PATH", data["paths"]["db_path"])),
        csv_path=Path(os.getenv("LOTTERY_CSV_PATH", data["paths"]["csv_path"])),
        default_window=int(
            os.getenv("LOTTERY_DEFAULT_WINDOW", data["analysis"]["default_window"])
        ),
        log_level=os.getenv("LOTTERY_LOG_LEVEL", data["logging"]["level"]),
    )


def setup_logging(level: str = "INFO") -> None:
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler("logs/app.log"), logging.StreamHandler()],
    )
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml config/config.toml src/lottery/__init__.py src/lottery/config.py tests/test_config.py
git commit -m "feat: project scaffolding, config loader, logging"
```

---

### Task 2: Data models + repository

**Files:**
- Create: `src/lottery/data/__init__.py` (empty)
- Create: `src/lottery/data/models.py`
- Create: `src/lottery/data/repository.py`
- Test: `tests/data/test_repository.py`

**Interfaces:**
- Produces: constants `ALL_COLUMNS: list[str]`, `NUMBER_COLUMNS: list[str]`, `INT_COLUMNS: list[str]`, `TABLE_NAME: str`; class `DrawRepository(db_path)` with `load() -> pd.DataFrame` (sorted oldest→newest, number cols `string` dtype with `pd.NA` for empties, `Year`/`Month` int64).

- [ ] **Step 1: Create `src/lottery/data/__init__.py`** (empty file)

- [ ] **Step 2: Create `src/lottery/data/models.py`**

```python
from __future__ import annotations

TABLE_NAME = "draws"

NUMBER_COLUMNS = [
    "FirstPrize",
    "Last2",
    "Front3_1",
    "Front3_2",
    "Back3_1",
    "Back3_2",
    "Back3_3",
    "Back3_4",
]
INT_COLUMNS = ["Year", "Month"]
ALL_COLUMNS = ["DrawDate", *INT_COLUMNS, *NUMBER_COLUMNS]
```

- [ ] **Step 3: Write the failing test** — `tests/data/__init__.py` (empty) and `tests/data/test_repository.py`

```python
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
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/data/test_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lottery.data.repository'`

- [ ] **Step 5: Write `src/lottery/data/repository.py`**

```python
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from lottery.data.models import ALL_COLUMNS, INT_COLUMNS, NUMBER_COLUMNS, TABLE_NAME

logger = logging.getLogger(__name__)


class DrawRepository:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    def load(self) -> pd.DataFrame:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Dataset not found: {self.db_path}")
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
        missing = [c for c in ALL_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Schema mismatch, missing columns: {missing}")
        for col in NUMBER_COLUMNS:
            df[col] = df[col].astype("string").replace({"": pd.NA})
        for col in INT_COLUMNS:
            df[col] = df[col].astype("int64")
        df = df.sort_values("DrawDate").reset_index(drop=True)
        logger.info("Loaded %d draws from %s", len(df), self.db_path)
        return df[ALL_COLUMNS]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/data/test_repository.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: Commit**

```bash
git add src/lottery/data tests/data
git commit -m "feat: draw schema and SQLite repository"
```

---

### Task 3: Feature engineering

**Files:**
- Create: `src/lottery/features/__init__.py` (empty)
- Create: `src/lottery/features/engineering.py`
- Test: `tests/features/test_engineering.py`

**Interfaces:**
- Consumes: a DataFrame with at least `FirstPrize` (string) and `Last2` (string) columns.
- Produces: `add_features(df: pd.DataFrame) -> pd.DataFrame` adding `fp_digit_sum`, `fp_odd_count`, `fp_even_count`, `fp_high_count`, `fp_low_count` (all `Int64`/`NA` for missing prize), `last2_int` (`Int64`).

- [ ] **Step 1: Create `src/lottery/features/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing test** — `tests/features/__init__.py` (empty) and `tests/features/test_engineering.py`

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/features/test_engineering.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lottery.features.engineering'`

- [ ] **Step 4: Write `src/lottery/features/engineering.py`**

```python
from __future__ import annotations

import pandas as pd


def _count(value: object, predicate) -> object:
    if pd.isna(value) or value == "":
        return pd.NA
    return sum(1 for d in str(value) if predicate(int(d)))


def _digit_sum(value: object) -> object:
    if pd.isna(value) or value == "":
        return pd.NA
    return sum(int(d) for d in str(value))


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    fp = out["FirstPrize"]
    out["fp_digit_sum"] = fp.map(_digit_sum).astype("Int64")
    out["fp_odd_count"] = fp.map(lambda v: _count(v, lambda d: d % 2 == 1)).astype("Int64")
    out["fp_even_count"] = fp.map(lambda v: _count(v, lambda d: d % 2 == 0)).astype("Int64")
    out["fp_high_count"] = fp.map(lambda v: _count(v, lambda d: d >= 5)).astype("Int64")
    out["fp_low_count"] = fp.map(lambda v: _count(v, lambda d: d < 5)).astype("Int64")
    out["last2_int"] = pd.to_numeric(out["Last2"], errors="coerce").astype("Int64")
    return out
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/features/test_engineering.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/lottery/features tests/features
git commit -m "feat: feature engineering for first prize and last2"
```

---

### Task 4: Stats — summary (entropy, chi-square, describe)

**Files:**
- Create: `src/lottery/stats/__init__.py` (empty)
- Create: `src/lottery/stats/summary.py`
- Test: `tests/stats/test_summary.py`

**Interfaces:**
- Produces: `shannon_entropy(counts: pd.Series) -> float`; `chi_square_uniform(counts: pd.Series, categories: int) -> tuple[float, float]` returning `(statistic, p_value)`; `describe_numeric(series: pd.Series) -> dict[str, float]` with keys `mean, median, mode, variance, std`; `correlation_matrix(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame` (Pearson correlation over the given numeric columns).

- [ ] **Step 1: Create `src/lottery/stats/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing test** — `tests/stats/__init__.py` (empty) and `tests/stats/test_summary.py`

```python
import pandas as pd

from lottery.stats.summary import chi_square_uniform, describe_numeric, shannon_entropy


def test_shannon_entropy_uniform():
    assert shannon_entropy(pd.Series([1, 1, 1, 1])) == 2.0


def test_chi_square_uniform_perfect_fit():
    stat, p = chi_square_uniform(pd.Series([10, 10, 10, 10]), 4)
    assert stat == 0.0
    assert round(p, 6) == 1.0


def test_describe_numeric():
    d = describe_numeric(pd.Series([1, 2, 2, 3]))
    assert d["mean"] == 2.0
    assert d["mode"] == 2.0
    assert d["median"] == 2.0


def test_correlation_matrix():
    from lottery.stats.summary import correlation_matrix

    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 4, 6, 8], "c": [4, 3, 2, 1]})
    corr = correlation_matrix(df, ["a", "b", "c"])
    assert round(corr.loc["a", "b"], 6) == 1.0
    assert round(corr.loc["a", "c"], 6) == -1.0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/stats/test_summary.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lottery.stats.summary'`

- [ ] **Step 4: Write `src/lottery/stats/summary.py`**

```python
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


def shannon_entropy(counts: pd.Series) -> float:
    total = counts.sum()
    if total == 0:
        return 0.0
    p = counts[counts > 0] / total
    return float(-(p * np.log2(p)).sum())


def chi_square_uniform(counts: pd.Series, categories: int) -> tuple[float, float]:
    observed = counts.to_numpy(dtype=float)
    if len(observed) < categories:
        observed = np.concatenate([observed, np.zeros(categories - len(observed))])
    expected = np.full(categories, observed.sum() / categories)
    stat, p = scipy_stats.chisquare(observed, expected)
    return float(stat), float(p)


def describe_numeric(series: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return {k: float("nan") for k in ("mean", "median", "mode", "variance", "std")}
    return {
        "mean": float(s.mean()),
        "median": float(s.median()),
        "mode": float(s.mode().iloc[0]),
        "variance": float(s.var(ddof=0)),
        "std": float(s.std(ddof=0)),
    }


def correlation_matrix(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    numeric = df[columns].apply(pd.to_numeric, errors="coerce")
    return numeric.corr(method="pearson")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/stats/test_summary.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add src/lottery/stats/__init__.py src/lottery/stats/summary.py tests/stats
git commit -m "feat: summary stats (entropy, chi-square, describe)"
```

---

### Task 5: Stats — frequency, hot/cold, gap

**Files:**
- Create: `src/lottery/stats/frequency.py`
- Test: `tests/stats/test_frequency.py`

**Interfaces:**
- Produces: `frequency(series) -> pd.DataFrame[value, count, probability]` (desc by count); `hot_cold(series, top_n=10) -> tuple[pd.DataFrame, pd.DataFrame]` (hot, cold); `current_gap(series) -> pd.DataFrame[value, gap]` where `series` is chronological oldest→newest and `gap` = draws since the value last appeared (0 = newest draw).

- [ ] **Step 1: Write the failing test** — `tests/stats/test_frequency.py`

```python
import pandas as pd

from lottery.stats.frequency import current_gap, frequency, hot_cold


def test_frequency_counts_and_probability():
    f = frequency(pd.Series(["01", "01", "02", "03"]))
    top = f.iloc[0]
    assert top["value"] == "01"
    assert top["count"] == 2
    assert abs(top["probability"] - 0.5) < 1e-9


def test_hot_cold_split():
    hot, cold = hot_cold(pd.Series(["01", "01", "01", "02", "03"]), top_n=1)
    assert hot.iloc[0]["value"] == "01"
    assert cold.iloc[0]["count"] == 1


def test_current_gap():
    g = current_gap(pd.Series(["01", "02", "03", "02"]))
    assert g[g["value"] == "02"]["gap"].iloc[0] == 0
    assert g[g["value"] == "01"]["gap"].iloc[0] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/stats/test_frequency.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lottery.stats.frequency'`

- [ ] **Step 3: Write `src/lottery/stats/frequency.py`**

```python
from __future__ import annotations

import pandas as pd


def frequency(series: pd.Series) -> pd.DataFrame:
    counts = series.dropna().value_counts()
    total = counts.sum()
    df = counts.rename("count").reset_index()
    df.columns = ["value", "count"]
    df["probability"] = df["count"] / total if total else 0.0
    return df.sort_values("count", ascending=False).reset_index(drop=True)


def hot_cold(series: pd.Series, top_n: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    freq = frequency(series)
    hot = freq.head(top_n).reset_index(drop=True)
    cold = freq.sort_values("count").head(top_n).reset_index(drop=True)
    return hot, cold


def current_gap(series: pd.Series) -> pd.DataFrame:
    s = series.reset_index(drop=True)
    n = len(s)
    last_index: dict[object, int] = {}
    for i, value in s.items():
        if pd.notna(value):
            last_index[value] = i
    rows = [{"value": v, "gap": n - 1 - idx} for v, idx in last_index.items()]
    return pd.DataFrame(rows).sort_values("gap", ascending=False).reset_index(drop=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/stats/test_frequency.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/lottery/stats/frequency.py tests/stats/test_frequency.py
git commit -m "feat: frequency, hot/cold, and gap analysis"
```

---

### Task 6: Stats — digit pair & triple frequency

**Files:**
- Create: `src/lottery/stats/pairs.py`
- Test: `tests/stats/test_pairs.py`

**Interfaces:**
- Produces: `digit_pair_frequency(series) -> pd.DataFrame[pair, count]` and `digit_triple_frequency(series) -> pd.DataFrame[triple, count]`; pairs/triples are sorted-digit combinations within each number string, joined by `-` (e.g. `"1-2"`).

- [ ] **Step 1: Write the failing test** — `tests/stats/test_pairs.py`

```python
import pandas as pd

from lottery.stats.pairs import digit_pair_frequency, digit_triple_frequency


def test_digit_pair_frequency():
    f = digit_pair_frequency(pd.Series(["12", "21"]))
    assert f.iloc[0]["pair"] == "1-2"
    assert f.iloc[0]["count"] == 2


def test_digit_triple_frequency():
    f = digit_triple_frequency(pd.Series(["123"]))
    assert set(f["triple"]) == {"1-2-3"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/stats/test_pairs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lottery.stats.pairs'`

- [ ] **Step 3: Write `src/lottery/stats/pairs.py`**

```python
from __future__ import annotations

from itertools import combinations

import pandas as pd


def _combos(value: str, size: int) -> list[str]:
    return ["-".join(sorted(c)) for c in combinations(list(value), size)]


def _frequency(series: pd.Series, size: int, label: str) -> pd.DataFrame:
    rows: list[str] = []
    for value in series.dropna():
        rows.extend(_combos(str(value), size))
    counts = pd.Series(rows, dtype="object").value_counts()
    df = counts.rename("count").reset_index()
    df.columns = [label, "count"]
    return df


def digit_pair_frequency(series: pd.Series) -> pd.DataFrame:
    return _frequency(series, 2, "pair")


def digit_triple_frequency(series: pd.Series) -> pd.DataFrame:
    return _frequency(series, 3, "triple")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/stats/test_pairs.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/lottery/stats/pairs.py tests/stats/test_pairs.py
git commit -m "feat: digit pair and triple frequency"
```

---

### Task 7: Stats — digits (position, odd/even, high/low, mirror, running)

**Files:**
- Create: `src/lottery/stats/digits.py`
- Test: `tests/stats/test_digits.py`

**Interfaces:**
- Produces: `position_distribution(series) -> pd.DataFrame` (index 0–9 = digit, columns `pos_0..pos_{w-1}` = counts); `odd_even_ratio(series) -> pd.DataFrame[kind, count, ratio]`; `high_low_ratio(series) -> pd.DataFrame[kind, count, ratio]` (high = digit ≥ 5); `mirror_value(number: str) -> str` (0↔5,1↔6,2↔7,3↔8,4↔9); `is_ascending(number: str) -> bool`; `is_descending(number: str) -> bool`.

- [ ] **Step 1: Write the failing test** — `tests/stats/test_digits.py`

```python
import pandas as pd

from lottery.stats.digits import (
    high_low_ratio,
    is_ascending,
    is_descending,
    mirror_value,
    odd_even_ratio,
    position_distribution,
)


def test_position_distribution():
    d = position_distribution(pd.Series(["12", "13"]))
    assert d.loc[1, "pos_0"] == 2
    assert d.loc[2, "pos_1"] == 1


def test_odd_even_ratio():
    r = odd_even_ratio(pd.Series(["13"]))
    assert r[r["kind"] == "odd"]["count"].iloc[0] == 2
    assert r[r["kind"] == "even"]["count"].iloc[0] == 0


def test_high_low_ratio():
    r = high_low_ratio(pd.Series(["59"]))
    assert r[r["kind"] == "high"]["count"].iloc[0] == 2


def test_mirror_value():
    assert mirror_value("012") == "567"


def test_running_numbers():
    assert is_ascending("123") is True
    assert is_descending("321") is True
    assert is_ascending("122") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/stats/test_digits.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lottery.stats.digits'`

- [ ] **Step 3: Write `src/lottery/stats/digits.py`**

```python
from __future__ import annotations

import pandas as pd

MIRROR_MAP = {
    "0": "5", "1": "6", "2": "7", "3": "8", "4": "9",
    "5": "0", "6": "1", "7": "2", "8": "3", "9": "4",
}


def position_distribution(series: pd.Series) -> pd.DataFrame:
    s = series.dropna().astype(str)
    width = int(s.map(len).max()) if not s.empty else 0
    data = {f"pos_{p}": [0] * 10 for p in range(width)}
    for value in s:
        for p, digit in enumerate(value):
            data[f"pos_{p}"][int(digit)] += 1
    df = pd.DataFrame(data, index=range(10))
    df.index.name = "digit"
    return df


def _ratio_table(series: pd.Series, predicate, true_label: str, false_label: str) -> pd.DataFrame:
    yes = no = 0
    for value in series.dropna():
        for digit in str(value):
            if predicate(int(digit)):
                yes += 1
            else:
                no += 1
    total = yes + no
    return pd.DataFrame(
        [
            {"kind": true_label, "count": yes, "ratio": yes / total if total else 0.0},
            {"kind": false_label, "count": no, "ratio": no / total if total else 0.0},
        ]
    )


def odd_even_ratio(series: pd.Series) -> pd.DataFrame:
    return _ratio_table(series, lambda d: d % 2 == 1, "odd", "even")


def high_low_ratio(series: pd.Series) -> pd.DataFrame:
    return _ratio_table(series, lambda d: d >= 5, "high", "low")


def mirror_value(number: str) -> str:
    return "".join(MIRROR_MAP[d] for d in number)


def is_ascending(number: str) -> bool:
    return len(number) > 1 and all(
        int(number[i]) < int(number[i + 1]) for i in range(len(number) - 1)
    )


def is_descending(number: str) -> bool:
    return len(number) > 1 and all(
        int(number[i]) > int(number[i + 1]) for i in range(len(number) - 1)
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/stats/test_digits.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/lottery/stats/digits.py tests/stats/test_digits.py
git commit -m "feat: digit position, odd/even, high/low, mirror, running"
```

---

### Task 8: Stats — sequence (Markov transition, repeating digits)

**Files:**
- Create: `src/lottery/stats/sequence.py`
- Test: `tests/stats/test_sequence.py`

**Interfaces:**
- Produces: `markov_transition(series) -> pd.DataFrame` (10×10 row-stochastic matrix of digit→next-digit probabilities within each number; rows that never occur are all zero); `repeating_digit_counts(series) -> pd.DataFrame[max_repeat, count]` (distribution of the max same-digit repeat per number).

- [ ] **Step 1: Write the failing test** — `tests/stats/test_sequence.py`

```python
import pandas as pd

from lottery.stats.sequence import markov_transition, repeating_digit_counts


def test_markov_transition_rows_sum_to_one():
    m = markov_transition(pd.Series(["121"]))
    assert abs(m.loc[1, 2] - 1.0) < 1e-9
    assert abs(m.loc[2, 1] - 1.0) < 1e-9


def test_repeating_digit_counts():
    r = repeating_digit_counts(pd.Series(["112"]))
    assert r[r["max_repeat"] == 2]["count"].iloc[0] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/stats/test_sequence.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lottery.stats.sequence'`

- [ ] **Step 3: Write `src/lottery/stats/sequence.py`**

```python
from __future__ import annotations

import numpy as np
import pandas as pd


def markov_transition(series: pd.Series) -> pd.DataFrame:
    matrix = np.zeros((10, 10))
    for value in series.dropna():
        text = str(value)
        for i in range(len(text) - 1):
            matrix[int(text[i])][int(text[i + 1])] += 1
    row_sums = matrix.sum(axis=1, keepdims=True)
    probs = np.divide(matrix, row_sums, out=np.zeros_like(matrix), where=row_sums != 0)
    return pd.DataFrame(probs, index=range(10), columns=range(10))


def repeating_digit_counts(series: pd.Series) -> pd.DataFrame:
    rows: list[int] = []
    for value in series.dropna():
        text = str(value)
        rows.append(max((text.count(d) for d in set(text)), default=0))
    counts = pd.Series(rows, dtype="int64").value_counts().sort_index()
    df = counts.rename("count").reset_index()
    df.columns = ["max_repeat", "count"]
    return df
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/stats/test_sequence.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/lottery/stats/sequence.py tests/stats/test_sequence.py
git commit -m "feat: Markov transition and repeating-digit stats"
```

---

### Task 9: Dashboard — chart builders + Streamlit app

**Files:**
- Create: `src/lottery/dashboard/__init__.py` (empty)
- Create: `src/lottery/dashboard/components/__init__.py` (empty)
- Create: `src/lottery/dashboard/components/charts.py`
- Create: `src/lottery/dashboard/app.py`
- Test: `tests/dashboard/test_charts.py`

**Interfaces:**
- Consumes: `DrawRepository.load`, `add_features`, and all `stats.*` functions defined above.
- Produces (charts): `frequency_bar(freq: pd.DataFrame, title: str) -> go.Figure`; `heatmap_10x10(freq: pd.DataFrame, title: str) -> go.Figure` (expects `value` as 2-digit strings); `transition_heatmap(matrix: pd.DataFrame, title: str) -> go.Figure`.

- [ ] **Step 1: Create the empty `__init__.py` files**

Create empty: `src/lottery/dashboard/__init__.py`, `src/lottery/dashboard/components/__init__.py`, `tests/dashboard/__init__.py`.

- [ ] **Step 2: Write the failing test** — `tests/dashboard/test_charts.py`

```python
import pandas as pd

from lottery.dashboard.components.charts import (
    frequency_bar,
    heatmap_10x10,
    transition_heatmap,
)


def test_frequency_bar_builds_figure():
    freq = pd.DataFrame({"value": ["01", "02"], "count": [2, 1]})
    fig = frequency_bar(freq, "t")
    assert len(fig.data) == 1


def test_heatmap_10x10_shape():
    freq = pd.DataFrame({"value": ["00", "99"], "count": [3, 5]})
    fig = heatmap_10x10(freq, "t")
    z = fig.data[0].z
    assert len(z) == 10 and len(z[0]) == 10
    assert z[0][0] == 3
    assert z[9][9] == 5


def test_transition_heatmap_builds():
    matrix = pd.DataFrame([[0.5, 0.5], [1.0, 0.0]], index=[0, 1], columns=[0, 1])
    fig = transition_heatmap(matrix, "t")
    assert fig.data[0].z is not None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/dashboard/test_charts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lottery.dashboard.components.charts'`

- [ ] **Step 4: Write `src/lottery/dashboard/components/charts.py`**

```python
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def frequency_bar(freq: pd.DataFrame, title: str) -> go.Figure:
    return px.bar(freq, x="value", y="count", title=title)


def heatmap_10x10(freq: pd.DataFrame, title: str) -> go.Figure:
    grid = [[0] * 10 for _ in range(10)]
    for _, row in freq.iterrows():
        value = str(row["value"]).zfill(2)
        grid[int(value[0])][int(value[1])] = row["count"]
    return go.Figure(
        data=go.Heatmap(z=grid, x=list(range(10)), y=list(range(10))),
        layout=go.Layout(title=title),
    )


def transition_heatmap(matrix: pd.DataFrame, title: str) -> go.Figure:
    return go.Figure(
        data=go.Heatmap(z=matrix.to_numpy(), x=list(matrix.columns), y=list(matrix.index)),
        layout=go.Layout(title=title),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/dashboard/test_charts.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Write `src/lottery/dashboard/app.py`**

```python
from __future__ import annotations

import sys
from pathlib import Path

# Allow `streamlit run src/lottery/dashboard/app.py` to resolve the package.
SRC = Path(__file__).resolve().parents[2]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import streamlit as st

from lottery.config import load_config
from lottery.data.repository import DrawRepository
from lottery.features.engineering import add_features
from lottery.stats import digits, frequency, pairs, sequence, summary
from lottery.dashboard.components.charts import (
    frequency_bar,
    heatmap_10x10,
    transition_heatmap,
)

DISCLAIMER = (
    "ℹ️ ข้อมูลนี้เป็นการวิเคราะห์เชิงสถิติย้อนหลังเพื่อการศึกษาเท่านั้น "
    "หวยเป็นการสุ่ม ผลในอดีตไม่สามารถทำนายผลในอนาคตได้"
)

TARGET_COLUMNS = {
    "เลขท้าย 2 ตัว (Last2)": "Last2",
    "เลขหน้า 3 ตัว #1 (Front3_1)": "Front3_1",
    "เลขท้าย 3 ตัว #1 (Back3_1)": "Back3_1",
    "รางวัลที่ 1 (FirstPrize)": "FirstPrize",
}


@st.cache_data
def get_data() -> pd.DataFrame:
    cfg = load_config()
    return add_features(DrawRepository(cfg.db_path).load())


def main() -> None:
    st.set_page_config(page_title="สถิติหวย", layout="wide")
    st.title("📊 วิเคราะห์สถิติหวยย้อนหลัง (พ.ศ. 2533–2569)")
    st.warning(DISCLAIMER)

    df = get_data()

    st.sidebar.header("ตัวกรอง")
    years = sorted(df["Year"].unique())
    year_range = st.sidebar.select_slider(
        "ช่วงปี (พ.ศ.)", options=years, value=(years[0], years[-1])
    )
    target_label = st.sidebar.selectbox("เลือกประเภทเลข", list(TARGET_COLUMNS))
    target = TARGET_COLUMNS[target_label]
    window = st.sidebar.number_input(
        "Hot/Cold เฉพาะ N งวดล่าสุด (0 = ทั้งหมด)", min_value=0, value=0, step=10
    )

    mask = (df["Year"] >= year_range[0]) & (df["Year"] <= year_range[1])
    view = df[mask]
    if view.empty:
        st.info("ไม่พบข้อมูลในช่วงที่เลือก")
        return

    series = view[target].dropna()

    tabs = st.tabs(
        ["ภาพรวม", "ความถี่", "ช่วงห่าง", "หลักตัวเลข", "คู่/สามตัว", "แนวโน้ม"]
    )

    with tabs[0]:
        counts = frequency.frequency(series).set_index("value")["count"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("จำนวนงวด", len(view))
        c2.metric("ช่วงวันที่", f"{view.iloc[0]['DrawDate']} → {view.iloc[-1]['DrawDate']}")
        c3.metric("Entropy", f"{summary.shannon_entropy(counts):.3f}")
        if target == "Last2":
            _, p_value = summary.chi_square_uniform(counts, 100)
            c4.metric("χ² p-value (uniform)", f"{p_value:.3f}")
        st.dataframe(view.tail(20))

    with tabs[1]:
        freq = frequency.frequency(series)
        st.plotly_chart(frequency_bar(freq, f"ความถี่ {target_label}"), use_container_width=True)
        if target == "Last2":
            st.plotly_chart(heatmap_10x10(freq, "Heatmap 00–99"), use_container_width=True)
        hot_series = series.tail(int(window)) if window else series
        hot, cold = frequency.hot_cold(hot_series)
        col_hot, col_cold = st.columns(2)
        col_hot.subheader("เลขมาบ่อย (Hot)")
        col_hot.dataframe(hot)
        col_cold.subheader("เลขมาน้อย (Cold)")
        col_cold.dataframe(cold)

    with tabs[2]:
        st.subheader("ช่วงห่างตั้งแต่ออกครั้งล่าสุด")
        st.dataframe(frequency.current_gap(series))

    with tabs[3]:
        st.plotly_chart(
            transition_heatmap(
                digits.position_distribution(series).T, "การกระจายตัวตามตำแหน่งหลัก"
            ),
            use_container_width=True,
        )
        st.subheader("คี่/คู่")
        st.dataframe(digits.odd_even_ratio(series))
        st.subheader("สูง/ต่ำ")
        st.dataframe(digits.high_low_ratio(series))

    with tabs[4]:
        st.subheader("ความถี่คู่ตัวเลข")
        st.dataframe(pairs.digit_pair_frequency(series).head(20))
        st.subheader("ความถี่สามตัวเลข")
        st.dataframe(pairs.digit_triple_frequency(series).head(20))

    with tabs[5]:
        st.subheader("Markov Transition (หลัก → หลักถัดไป)")
        st.plotly_chart(
            transition_heatmap(sequence.markov_transition(series), "Markov Transition"),
            use_container_width=True,
        )
        yearly = view.groupby("Year").size().rename("draws").reset_index()
        st.subheader("จำนวนงวดต่อปี")
        st.bar_chart(yearly, x="Year", y="draws")
        monthly = view.groupby("Month").size().rename("draws").reset_index()
        st.subheader("จำนวนงวดต่อเดือน")
        st.bar_chart(monthly, x="Month", y="draws")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Manual verification — run the dashboard**

Run: `PYTHONPATH=src streamlit run src/lottery/dashboard/app.py`
Expected: browser opens; the disclaimer banner shows; all six tabs render without error for the default (full) year range; switching the target selector and year range updates charts.

- [ ] **Step 8: Run the full test suite**

Run: `pytest -q`
Expected: PASS (all tests green, ~20+ passed).

- [ ] **Step 9: Commit**

```bash
git add src/lottery/dashboard tests/dashboard
git commit -m "feat: Streamlit dashboard with chart builders and tabs"
```

---

## Notes for the implementer

- Install deps first: `pip install -e ".[dev]"` (or `pip install pandas numpy scipy plotly streamlit pytest ruff`).
- Run `ruff check src tests` before each commit; fix lint inline.
- The dataset already exists (`dataset/lottery_results.sqlite`, 872 rows). If it is missing, regenerate with `python3 scraper/scrape_myhora.py`.
- `stats` and `features` must stay free of `streamlit` and `sqlite3` imports — keep them pure so the later modeling sub-project can reuse them.
