# CLAUDE.md — Lottery Statistical Analysis Project

Guidance for AI assistants (and humans) working in this repository.

## What this project is

Statistical analysis and **experimental/educational** modeling of historical Thai
Government Lottery results (BE 2533–2569 / CE 1990–2026). Full requirements are in
`README.md`.

**Honest framing — keep this everywhere.** The Thai lottery is a near-uniform
random draw. Past results have **no predictive value** for future draws; no model
can beat chance on a fair lottery. All analysis is descriptive; any future
modeling is an explicitly-labelled experiment. Never present a number as likely to
be drawn. Score language only (probability/confidence/trend), never certainty.

## Current state (history)

- **2026-06-27 — Dataset built.** Scraped all 872 draws from
  `myhora.com/lottery/stats.aspx?mx=09&vx=40` (`vx` = years back from the latest
  draw; `vx=40` covers BE 2533–2569). Scraper: `scraper/scrape_myhora.py`
  (stdlib only, self-validates against two reference draws). Output:
  `dataset/lottery_results.csv` and `dataset/lottery_results.sqlite`
  (table `draws`, PK `DrawDate`). See `dataset/README.md` for the data dictionary.
  - Dates/years stored in the **Buddhist Era (BE)** calendar, matching the source.
  - Schema extends the README with nullable `Back3_3`/`Back3_4` because pre-2015
    draws have four back-3 numbers and no front-3 numbers.
  - 120 draws (~1994–1995) have a 7-digit first prize — a source characteristic,
    preserved verbatim.
- **2026-06-27 — Foundation design approved.** Spec:
  `docs/superpowers/specs/2026-06-27-lottery-foundation-design.md`. First
  sub-project = data layer + statistical engine + Streamlit dashboard
  (Approach A, pragmatic clean structure).
- **2026-06-27 — Implementation plan written.** 9-task bite-sized TDD plan:
  `docs/superpowers/plans/2026-06-27-lottery-foundation.md`.
- **2026-06-28 — Foundation build COMPLETE (Subagent-Driven Development).**
  All 9 tasks done and reviewed on branch **`feature/foundation`** (off `main`
  at `6cacc1d`; **kept as-is — not merged/pushed**, GitHub auth pending). HEAD
  `c9a2535`. **27/27 tests pass, ruff clean.** Per-task SDD: fresh implementer
  subagent → task review → fixes → next, then a whole-branch final review.
  Durable progress ledger: `.superpowers/sdd/progress.md`.
  - **Tasks 1–4** (HEAD was `e840d47`):
    - Task 1: scaffolding (`pyproject.toml`, `config/config.toml`,
      `src/lottery/config.py`) — `e3c3583`.
    - Task 2: data layer (`src/lottery/data/models.py`, `repository.py`) — `ba6b744`.
    - Task 3: feature engineering (`src/lottery/features/engineering.py`) — `ba1b53f`.
    - Task 4: summary stats (`src/lottery/stats/summary.py`: entropy, chi-square,
      describe_numeric, correlation_matrix) — `fc47bc7`, fix `e840d47`.
  - **Tasks 5–9** (this session):
    - Task 5: `src/lottery/stats/frequency.py` (frequency, hot/cold, current_gap) — `eccaa7f`.
    - Task 6: `src/lottery/stats/pairs.py` (digit pair & triple frequency) — `194602e`.
    - Task 7: `src/lottery/stats/digits.py` (position dist, odd/even, high/low,
      mirror, ascending/descending) — `b7cf93d`.
    - Task 8: `src/lottery/stats/sequence.py` (Markov transition, repeating-digit
      counts) — `9e3995a`.
    - Task 9: `src/lottery/dashboard/` (plotly chart builders + Thai Streamlit
      app with random-draw disclaimer) — `1b0bdb8`, fix `26f4697` (empty-series
      guard for pre-2015 all-NA columns; Thai-ized heatmap title).
  - **Final whole-branch review (opus):** no Critical. Two Important fixes
    applied: untracked machine-specific `.claude/settings.local.json` (now
    gitignored) — `936069c`; `current_gap` returns a well-formed empty frame on
    empty input (+ regression test) — `c9a2535`.
  - **Outstanding (non-blocking):**
    - Browser smoke check (2026-06-28): app loads in a headless Chromium with
      all tabs rendering and no exceptions; the overview tab was driven directly.
      A full per-tab click-through of the 6 Foundation tabs was not exhaustively
      exercised — see the 1.5 entry below for the browser-verification setup.
    - Deferred Minor review findings to triage in a later sub-project are listed
      in the progress ledger.
- **2026-06-28 — Sub-project 1.5 designed & planned (build pending).**
  "Live refresh + experimental suggestions" — two user requests
  (`USER_REQUEST.txt`): (1) incrementally fetch the latest draw(s); (2) suggest
  the most-likely numbers per prize category. Framing decided per the honesty
  rule: suggestions are **descriptive experimental scores only** (blended
  frequency + recency-gap + recent-trend, with breakdown), never a prediction,
  always shown with the random-draw disclaimer.
  - Spec: `docs/superpowers/specs/2026-06-28-live-refresh-and-suggestions-design.md`.
  - Plan: `docs/superpowers/plans/2026-06-28-live-refresh-and-suggestions.md`
    (8-task TDD plan, Approach A = refactor scraper parsing into
    `src/lottery/data/myhora.py`, kept stdlib-only).
  - Scope: `myhora.fetch_draws`; `DrawRepository.latest_date()`/`save()`;
    `data/updater.py` (`update_dataset`, `UpdateError`); config `[suggest]`;
    `stats/suggest.py` (last2/back3/front3/firstprize-last3 + per-digit);
    `cli.py` (`python -m lottery.cli update|suggest`); dashboard refresh button
    + "ตัวเลขน่าสนใจ" tab.
  - **Not yet implemented** — awaiting execution-mode choice (Subagent-Driven vs
    inline). Still on branch `feature/foundation`.
- **2026-06-28 — Sub-project 1.5 build COMPLETE (Subagent-Driven Development).**
  All 8 tasks done and reviewed on branch **`feature/foundation`** (kept as-is —
  not merged/pushed, per user choice). HEAD `fce2ece`. **52/52 tests pass, ruff
  clean.** Per-task SDD: fresh implementer subagent → task review → fixes → next,
  then a whole-branch final review (opus). Ledger: `.superpowers/sdd/progress.md`
  (Foundation ledger archived as `progress-foundation.md`). Sub-project commits
  span `b5228de..fce2ece`:
  - Task 1: `src/lottery/data/myhora.py` (stdlib-only fetch/parse extracted from
    the scraper, which is now a thin CLI) — `eb42548`.
  - Task 2: `DrawRepository.latest_date()` + `save()` (CSV+SQLite, NA→NULL
    roundtrip; sole disk writer) — `eabea06`, fix `3a4088b` (latest_date returns
    None when `draws` table missing).
  - Task 3: `src/lottery/data/updater.py` (`update_dataset`, `UpdateReport`,
    `UpdateError`; merges only draws newer than the latest stored) — `6df4d23`.
  - Task 4: config `[suggest]` (`top_n`/`recent_window`/`weights`) + tidy
    `config.py` — `8efaa23`.
  - Task 5: `src/lottery/stats/suggest.py` (`score_candidates` blended
    frequency/recency/trend + Thai/English `DISCLAIMER`) — `f594560`.
  - Task 6: per-category suggestions (`CATEGORIES`, `suggest_category`,
    `firstprize_digit_frequency`, `suggest_all`) — `889727b`.
  - Task 7: `src/lottery/cli.py` (`python -m lottery.cli update|suggest`) +
    `[project.scripts]` — `fda5e43`.
  - Task 8: dashboard `suggestion_bar` chart + sidebar refresh button +
    "ตัวเลขน่าสนใจ" tab (renders `DISCLAIMER`, uses full history) — `41286b4`.
  - **Final whole-branch review (opus):** integration seams all clean (NA
    roundtrip, stdlib-only `myhora`, disclaimer on both CLI+dashboard, consistent
    kwargs/schema/`DrawResult` order). One **Important** cross-cutting defect
    found + fixed — `fce2ece`: `back3`/`front3` recency/trend were computed on a
    column-stacked (non-chronological) series, so time signals reflected pre-2015
    `Back3_3`/`Back3_4` data; fixed with a row-major `ravel("C")` reshape
    (chronological, per-draw-adjacent) + a discriminating regression test
    (re-review live-verified: fails old code, passes new). Same commit fixed a
    dangling `myhora` docstring cross-ref and added a 7-digit-FirstPrize exclusion
    test.
  - **Outstanding (non-blocking):**
    - Browser-verified (2026-06-28, PASS). Drove the live Streamlit app in a
      headless Chromium and confirmed: all 7 tabs render (incl. the new
      "ตัวเลขน่าสนใจ"); the suggestions tab shows the non-predictive DISCLAIMER
      adjacent to a `score` bar chart + breakdown table (freq/recency/trend, all
      4 categories + first-prize digit table, leading zeros preserved); the
      "🔄 อัปเดตข้อมูลล่าสุด" button runs a live myhora fetch and shows the Thai
      "ข้อมูลเป็นปัจจุบันแล้ว" result with no console errors/exceptions.
      Setup: Playwright has no Chromium build for this host's ubuntu26.04 tag, so
      the server ran in WSL (`localhost:8501`) driven by a Windows-side
      Playwright/Chromium via WSL2 localhost forwarding (temp tooling, since
      removed; venv restored to its documented package set).
    - Deferred Minor review findings to triage in a later sub-project are listed
      in the progress ledger (e.g. de-duplicate the default weights between
      `config.py` and `suggest.py`).

## Environment / how to run

- **Dependencies live in the project venv `.venv`, NOT system `python3`**
  (system Python 3.14.4 has no `pip`/`ensurepip`; pip was bootstrapped into
  `.venv` via `get-pip.py`). Installed: pandas 3.0.3, numpy 2.5, scipy 1.18,
  plotly 6.8, streamlit 1.58, pytest 9.1, ruff 0.15.
- Run tests from the repo root with **`.venv/bin/pytest`** (pyproject sets
  `pythonpath = ["src"]`). Lint with `.venv/bin/ruff check src tests`.
- Run the dashboard: `PYTHONPATH=src .venv/bin/streamlit run src/lottery/dashboard/app.py`.
- Note: pandas is **3.0** (not 2.x) — watch for API differences vs. the plan's
  reference snippets.

## Planned decomposition (sub-projects)

1. **Foundation** (current): data layer, statistical engine, dashboard.
2. Pattern mining (Apriori / FP-Growth / association rules / clustering).
3. ML / DL / time-series modeling (experimental).
4. Monte-Carlo simulation.
5. REST API + exports.

## Conventions

- Python 3.13+ (developed on 3.14). Type hints, PEP8, `ruff`.
- Number fields (`FirstPrize`, `Last2`, `Front3_*`, `Back3_*`) are **strings** to
  preserve leading zeros; empty era cells are `pandas.NA`, never `0`.
- Dependency direction (foundation): `dashboard → stats → features → data`.
  Only `repository` touches SQLite; `features`/`stats` are pure and unit-tested.
- Regenerate the dataset with `python3 scraper/scrape_myhora.py`.

## Process

This project uses the Superpowers workflow: brainstorm → spec
(`docs/superpowers/specs/`) → implementation plan → build with TDD. Each
sub-project gets its own spec and plan.
