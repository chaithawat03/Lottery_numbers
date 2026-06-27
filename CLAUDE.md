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
- **2026-06-27 — Foundation build in progress (Subagent-Driven Development).**
  Working on branch **`feature/foundation`** (off `main` at `6cacc1d`; not yet
  pushed — GitHub auth pending). Per-task SDD: fresh implementer subagent →
  task review → fixes → next. Durable progress ledger:
  `.superpowers/sdd/progress.md`.
  - **Done & reviewed clean: Tasks 1–4.** Current HEAD `e840d47`.
    - Task 1: scaffolding (`pyproject.toml`, `config/config.toml`,
      `src/lottery/config.py`) — `e3c3583`.
    - Task 2: data layer (`src/lottery/data/models.py`, `repository.py`) — `ba6b744`.
    - Task 3: feature engineering (`src/lottery/features/engineering.py`) — `ba1b53f`.
    - Task 4: summary stats (`src/lottery/stats/summary.py`: entropy, chi-square,
      describe_numeric, correlation_matrix) — `fc47bc7`, fix `e840d47`
      (documented+tested `ddof=0` population stats; guarded chi-square input).
  - **Not started: Tasks 5–9** (stats: frequency, pairs, digits, sequence;
    then dashboard). Resume by dispatching the Task 5 implementer
    (`src/lottery/stats/frequency.py`).
  - After Task 9: final whole-branch code review, then
    `superpowers:finishing-a-development-branch`.
  - Deferred Minor review findings to triage at final review are listed in the
    progress ledger.

## Environment / how to run

- **Dependencies live in the project venv `.venv`, NOT system `python3`**
  (system Python 3.14.4 has no `pip`/`ensurepip`; pip was bootstrapped into
  `.venv` via `get-pip.py`). Installed: pandas 3.0.3, numpy 2.5, scipy 1.18,
  plotly 6.8, streamlit 1.58, pytest 9.1, ruff 0.15.
- Run tests from the repo root with **`.venv/bin/pytest`** (pyproject sets
  `pythonpath = ["src"]`). Lint with `.venv/bin/ruff check src tests`.
- Run the dashboard (after Task 9): `PYTHONPATH=src .venv/bin/streamlit run src/lottery/dashboard/app.py`.
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
