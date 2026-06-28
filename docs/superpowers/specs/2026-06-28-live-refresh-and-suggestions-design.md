# Spec — Live Refresh & Experimental Suggestions

- **Date:** 2026-06-28
- **Sub-project:** Foundation extension (#1.5) — "Live refresh + experimental suggestions"
- **Branch base:** `feature/foundation`
- **Status:** Approved design, pre-implementation

## Honesty framing (non-negotiable)

The Thai Government Lottery is a near-uniform random draw. Past results have **no
predictive value**. Everything in this sub-project is **descriptive**. The
suggestion feature ranks candidates by *historical signals only* and is surfaced
as **experimental scores with a prominent random-draw disclaimer** — never as a
prediction, never with the word "probability of being drawn", never presenting a
number as likely to win. This requirement overrides any wording convenience.

## Goals

Two user-requested functions (`USER_REQUEST.txt` / `USER_REQUEST_TH.txt`):

1. **Retrieve the latest draw data** — keep the dataset current by fetching from
   myhora and **incrementally** merging only draws newer than the latest stored
   `DrawDate`.
2. **Suggest the most likely numbers per prize category** — descriptive blended
   score (frequency + recency-gap + recent-trend), with a component breakdown,
   for every meaningful category, wrapped in the disclaimer.

Both features are surfaced in **the Streamlit dashboard and a CLI**.

## Non-goals

- No true prediction / no claim of beating chance.
- No ML/DL models (that is sub-project 3 — this leaves room but does not build it).
- No ranking of the full 6-digit `FirstPrize` (1,000,000 combinations, ~one
  occurrence each — meaningless). Only its last-3 and per-position digits.
- No scheduler/cron auto-refresh; refresh is user-triggered (button / CLI).

## Architecture (Approach A — refactor for reuse)

Dependency direction stays `dashboard → stats → features → data`; **only
`repository` touches SQLite/disk**.

### Request #1 — data refresh

**New `src/lottery/data/myhora.py`** (stdlib-only — preserves the scraper's
no-heavy-deps property):

- `DrawResult` dataclass, `fetch_html(url)`, `parse_rows(html)`,
  `validate(results)` — moved verbatim out of `scraper/scrape_myhora.py`.
- `fetch_draws(url=STATS_URL) -> list[DrawResult]` — fetch → parse → validate →
  return sorted by `DrawDate`.

**`scraper/scrape_myhora.py`** becomes a thin CLI that imports parsing from
`lottery.data.myhora` and keeps `write_csv` / `write_sqlite` / `main` so the
full from-scratch bootstrap still works standalone.

**`src/lottery/data/repository.py`** gains:

- `latest_date() -> str | None` — max `DrawDate` in the DB, or `None` if empty.
- `save(df) -> None` — write a full DataFrame to **both** SQLite
  (`INSERT OR REPLACE` into `draws`) and the CSV, sorted by `DrawDate`. Keeps
  repository as the sole owner of SQLite/disk writes.

**New `src/lottery/data/updater.py`:**

- `@dataclass UpdateReport` — `added: int`, `latest_before: str | None`,
  `latest_after: str | None`, `new_dates: list[str]`.
- `update_dataset(repo, *, source=fetch_draws) -> UpdateReport` — load current
  data; read `latest_date()`; fetch from `source`; keep only rows with
  `DrawDate > latest_before`; merge + dedupe on `DrawDate` (existing rows win on
  conflict); `repo.save(merged)`. **Idempotent**: re-running with no new draws
  returns `added == 0` and does not corrupt the dataset.
- `source` is injectable so tests pass canned `DrawResult` lists (no network).
- `class UpdateError(Exception)` — raised on network/HTTP failure with a clear
  message; callers (dashboard) catch it. Parse/layout breakage still raises
  loudly through `validate`.

### Request #2 — suggestions

**New `src/lottery/stats/suggest.py`** (pure; depends on `stats.frequency` and
`features`):

- `score_candidates(series, *, weights, recent_window) -> DataFrame` — columns
  `value, freq_score, recency_score, trend_score, score`. Each signal min-max
  normalized to 0–1, then combined as a weighted sum into `score`; sorted by
  `score` descending. Signals:
  - **freq** — overall historical count of the value.
  - **recency** — inverse of current gap (smaller gap ⇒ higher), via
    `stats.frequency.current_gap`.
  - **trend** — count within the last `recent_window` draws.
  - Edge cases: empty/all-NA series ⇒ well-formed empty frame; a single distinct
    value ⇒ normalization avoids divide-by-zero (treat range 0 as score 0 or 1
    consistently).
- `suggest_category(df, category, *, weights, recent_window, top_n) -> DataFrame`
  — constructs the right series per `category`:
  - `last2` → `Last2`
  - `back3` → concatenation of `Back3_1..Back3_4` (drops NA)
  - `front3` → concatenation of `Front3_1`, `Front3_2` (sparse, post-2015 only)
  - `firstprize_last3` → last 3 chars of `FirstPrize`
  - `firstprize_digits` → per-position digit (0–9) frequency table (separate
    shape; documented in the function)
- `suggest_all(df, config) -> dict[str, DataFrame]` — runs every category, top-N
  each.
- Module-level `DISCLAIMER` constant (Thai + English) reused by all surfaces.

**Honesty enforcement:** every output path renders `DISCLAIMER` adjacent to the
numbers; the score column is named `score`, never anything implying real odds.

### Surfaces

**Config** — new `[suggest]` table in `config/config.toml` and matching fields on
the `Config` dataclass (`src/lottery/config.py`):

- `top_n` (default `10`)
- `recent_window` (default `50` draws)
- `weights` — `frequency` `0.5`, `recency` `0.25`, `trend` `0.25` (must be
  readable as a dict of floats)

**Dashboard** (`src/lottery/dashboard/app.py`, `components/charts.py`):

- Sidebar **"🔄 Refresh data"** button → `update_dataset`, spinner, result
  message ("Added N new draws (… → …)" / "Already up to date"), then clears the
  cached data load so charts refresh. `UpdateError` shown as an error message,
  not a crash.
- New **"Suggestions / ตัวเลขน่าสนใจ"** tab: per-category top-N bar charts +
  breakdown tables, with the disclaimer banner pinned at the top of the tab.

**CLI** — new `src/lottery/cli.py`, registered via `[project.scripts]` in
`pyproject.toml`:

- `lottery-update` → `lottery.cli:update_main` — run updater, print `UpdateReport`.
- `lottery-suggest` → `lottery.cli:suggest_main` — print top-N per category,
  followed by the disclaimer.

## Data flow

```
Refresh:  button/CLI → updater.update_dataset → myhora.fetch_draws (network)
                                              → repo.latest_date / load
                                              → merge+dedupe → repo.save (CSV+SQLite)
Suggest:  dashboard tab / CLI → repo.load → suggest.suggest_all(df, config)
                                          → render top-N + DISCLAIMER
```

## Error handling

- Network/HTTP failure during refresh → `UpdateError` with a clear message;
  dashboard catches and displays it; CLI exits non-zero with the message.
- myhora layout change → `validate` raises loudly (existing behavior preserved).
- Empty / all-NA category (e.g. pre-2015 Front3 only) → suggestions return a
  well-formed empty frame; surfaces show "no data for this category".
- Missing dataset file → existing `FileNotFoundError` from `repository.load`.

## Testing (TDD, run with `.venv/bin/pytest`)

- `myhora.parse_rows` / `validate` — keep the two reference-draw assertions after
  the move.
- `repository` — `latest_date` and `save` round-trip on a temp DB (+ CSV).
- `updater` — filter-newer, merge, dedupe, idempotency, and `UpdateError` path,
  all with an injected fake source (no network).
- `suggest` — normalization math, weighting, ordering, per-category series
  construction, single-value and empty/NA edge cases.
- Dashboard chart builders — pure-function smoke tests matching existing style.
- `ruff check src tests` clean.

## Conventions reminder

- Number fields stay **strings** (leading zeros); empty era cells are
  `pandas.NA`, never `0`.
- pandas is **3.0** — watch for API differences from older snippets.
- Dates remain in the **Buddhist Era** calendar, matching the source.
