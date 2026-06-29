# Design — Flask refactor + "My Tickets" tracking

**Date:** 2026-06-29
**Sub-project:** 2 (web) — replaces the Streamlit dashboard with Flask + HTML +
JavaScript and adds a personal ticket-tracking page.

> **Honesty rule (project-wide).** The Thai lottery is a near-uniform random
> draw; past results have no predictive value. Everything here is descriptive /
> experimental. The non-predictive DISCLAIMER renders on every page, on the
> suggestions panel, and near any "winnings" figure. Never present a number as
> likely to be drawn.

## Motivation

Two user requests (`USER_REQUEST.txt`):

1. **Refactor** the UI from Streamlit to **Python Flask + HTML + JavaScript**.
   The user finds Streamlit inconvenient.
2. **New feature** — a page that records the tickets the user actually *bought*
   for a draw, stored as a `.json` file holding `[number, draw, price]` (plus
   category), for further analysis.

## Decisions (from brainstorming)

- **Refactor fidelity:** full parity on all 7 existing analysis tabs, charts via
  **Plotly.js** in the browser (Flask emits Plotly figure JSON).
- **Architecture:** Approach A — Flask app-factory + blueprints, Jinja page
  shells + a JSON chart/data API, pure unit-tested ticket modules.
- **Ticket fields:** `number`, `draw_date`, `price`, `category`
  (`Last2 | Back3 | Front3 | FirstPrize`).
- **Ticket analysis:** auto win/loss check, spending summary, overlap vs the
  app's statistical suggestions, plus plain store + list.
- **Draw identity:** user picks a `DrawDate` from the dataset (dropdown); win/loss
  resolves immediately against that draw's stored numbers.
- **Storage:** single file `dataset/my_tickets.json`, path in `config.toml`,
  **git-ignored** (personal bets not committed).
- **Winnings:** standard official per-80-baht payout rates stored in
  `config.toml [payout]`, scaled by `price / 80`.
- **Streamlit:** removed once Flask reaches parity (`dashboard/` package +
  `streamlit` dependency dropped). Single stack.

## Architecture

The pure layers are **untouched**: `data/`, `features/`, `stats/` (existing
modules), `config.py`, `cli.py`, `data/updater.py`. Only the presentation layer
changes, plus a new pure ticket layer. Dependency direction is preserved:
`web → stats/tickets → tickets/store → data`, and `web → stats → features → data`.

```
src/lottery/
  web/
    __init__.py            # create_app() application factory
    blueprints/
      __init__.py
      analysis.py          # analysis page + /api/analysis/* JSON endpoints + /api/update
      tickets.py           # tickets page + /api/tickets/* JSON endpoints
    charts.py              # Plotly figure builders returning fig.to_dict()
    state.py               # memoized DataFrame load + clear() on update
    templates/
      base.html            # shared shell, nav, DISCLAIMER banner
      analysis.html        # 7-tab analysis shell
      tickets.html         # My Tickets page shell
    static/
      css/style.css
      js/charts.js         # Plotly.newPlot helpers
      js/analysis.js       # fetch + render the 7 tabs
      js/tickets.js        # ticket form, table, summary
  tickets/
    __init__.py
    models.py              # TicketRecord dataclass
    store.py               # pure JSON load/save/add/delete (sole writer)
  stats/
    tickets.py             # pure win/loss + spending + overlap analysis
```

`charts.py` reuses the current Plotly chart definitions (`frequency_bar`,
`heatmap_10x10`, `transition_heatmap`, `suggestion_bar`) but returns
`fig.to_dict()` — a JSON-serializable dict the browser renders with
`Plotly.newPlot`. No server-side image rendering.

### Run / deps
- Run: `PYTHONPATH=src .venv/bin/flask --app lottery.web run` (debug for dev).
  A `[project.scripts]` entry / CLI convenience may wrap this.
- `pyproject.toml`: add `flask`, remove `streamlit`. Plotly stays (figure
  construction). `plotly` JS is loaded in the browser via CDN or vendored static.
- `CLAUDE.md` "how to run" updated to the Flask command.

## Data flow

1. Browser loads a Jinja shell (`/` = analysis, `/tickets`). `base.html` renders
   the DISCLAIMER on every page.
2. JS fetches JSON from the API, e.g.
   `GET /api/analysis/frequency?target=Last2&year_from=2533&year_to=2569&window=0`.
   The endpoint runs the existing stats functions on the (filtered) DataFrame and
   returns `{ "figure": <plotly dict>, "table": [ ... ] }`.
3. `charts.js` calls `Plotly.newPlot(el, figure.data, figure.layout)`; tables
   render as HTML.
4. The DataFrame is loaded once and memoized in `web/state.py`. The **refresh**
   button issues `POST /api/update` → `update_dataset(repo)` → `state.clear()` →
   returns the Thai report (`เพิ่ม N งวด ...` / `ข้อมูลเป็นปัจจุบันแล้ว` /
   `อัปเดตไม่สำเร็จ: ...`).

### Analysis endpoints (parity with current Streamlit tabs)

| Tab (Thai)        | Endpoint                          | Returns |
|-------------------|-----------------------------------|---------|
| ภาพรวม Overview    | `/api/analysis/overview`          | metrics (draw count, date range, entropy, χ² p-value for Last2), recent rows |
| ความถี่ Frequency  | `/api/analysis/frequency`         | frequency bar; 10×10 heatmap (Last2); hot/cold tables (window) |
| ช่วงห่าง Gap        | `/api/analysis/gap`               | current-gap table |
| หลักตัวเลข Digits   | `/api/analysis/digits`            | position-distribution heatmap; odd/even; high/low |
| คู่/สามตัว Pairs    | `/api/analysis/pairs`             | digit pair + triple frequency (top 20) |
| แนวโน้ม Trend       | `/api/analysis/trend`             | Markov heatmap; draws per year; per month |
| ตัวเลขน่าสนใจ Suggest | `/api/analysis/suggestions`      | `suggest_all` per category + first-prize digit table; DISCLAIMER |

Shared query params (where relevant): `target`, `year_from`, `year_to`,
`window`. `target ∈ {Last2, Front3_1, Back3_1, FirstPrize}` mirrors the current
selector.

## My Tickets feature

### TicketRecord (`tickets/models.py`)
```json
{
  "id": "uuid4",
  "number": "23",
  "category": "Last2",
  "draw_date": "<BE DrawDate present in the dataset>",
  "price": 80.0,
  "created_at": "ISO-8601"
}
```
`number` is a string (leading zeros preserved). `category ∈ {Last2, Back3,
Front3, FirstPrize}`. `draw_date` must be an existing dataset `DrawDate`.

### Store (`tickets/store.py`) — pure, sole writer of the JSON file
- `load(path) -> list[TicketRecord]` — missing/empty file → `[]`.
- `save(path, records)` — writes the JSON array (UTF-8, `ensure_ascii=False`).
- `add(path, record)`, `delete(path, ticket_id)` — load → mutate → save.
- Never writes `0` for empty; numbers stay strings.

### Analysis (`stats/tickets.py`) — pure, unit-tested
Inputs: `records`, the draws `DataFrame`, payout rates, and (for overlap) the
suggestion results.

- **Win/loss** per ticket — look up the `draw_date` row, match `number`:
  - `Last2` → exact match of `Last2`.
  - `Back3` → matches **any** of `Back3_1..Back3_4` present (pre-2015 has up to 4).
  - `Front3` → matches **any** of `Front3_1`, `Front3_2`.
  - `FirstPrize` → exact match of `FirstPrize`.
  - Result fields: `status ∈ {hit, miss}`, `matched_field`, `winnings`.
  - **Winnings** = `payout[category] × (price / 80)` (official per-80-baht rate),
    `0` on miss.
- **Spending summary** — total spent; spent & winnings by category and by draw;
  net = total winnings − total spent. (Net is descriptive, not advice.)
- **Suggestion overlap** — for each ticket, whether `number` appears in
  `suggest_all(...)` output for the aligned suggestion category
  (`overlap: bool`, plus rank if present). Category mapping:
  `Last2→last2`, `Back3→back3`, `Front3→front3`, and `FirstPrize→firstprize_last3`
  comparing the ticket number's **last 3 digits** (suggestions only score the
  first prize's last 3). When lengths can't align, `overlap` is `null`.

Because the draw is always a known dataset date, every ticket is resolvable
(no "pending" state in this sub-project).

### Endpoints (`web/blueprints/tickets.py`)
- `GET  /tickets`            — Jinja page shell.
- `GET  /api/tickets`        — list tickets enriched with win/loss + overlap.
- `POST /api/tickets`        — validate + `store.add`; 400 on bad input
  (unknown category, `draw_date` not in dataset, non-numeric/empty number,
  non-positive price).
- `DELETE /api/tickets/<id>` — `store.delete`; 404 if missing.
- `GET  /api/tickets/summary` — spending summary card data.
- `GET  /api/draw-dates`     — dataset `DrawDate`s for the dropdown.

### UI (`tickets.html` + `tickets.js`)
Form (number, category, draw-date dropdown from `/api/draw-dates`, price) →
`POST`. Table of saved tickets with status (hit/miss), matched field, estimated
winnings, overlap flag, and delete. A spending-summary card (total spent, total
winnings, net, per-category). DISCLAIMER shown near winnings/net.

## Config additions (`config/config.toml`, `config.py`)
```toml
[paths]
tickets_path = "dataset/my_tickets.json"

[payout]            # standard official payout per single 80-baht ticket
ticket_unit = 80
Last2 = 2000
Back3 = 4000
Front3 = 4000
FirstPrize = 6000000
```
`Config` gains `tickets_path: Path` and `payout: dict[str, float]` (with
`ticket_unit`). Env overrides follow the existing `LOTTERY_*` pattern
(`LOTTERY_TICKETS_PATH`).

## Error handling
- API returns JSON `{ "error": "<message>" }` with an appropriate status (400
  bad request, 404 not found) on invalid input.
- `update_dataset` failures surface the existing Thai `UpdateError` message.
- Missing/empty `my_tickets.json` → empty list; the file is created on first save.
- Existing empty-series / pre-2015 all-NA guards in `stats` are preserved; the
  API passes their results through unchanged.

## Testing (TDD)
- `tickets/store.py` — round-trip load/save, leading-zero preservation,
  missing-file → `[]`, add/delete.
- `stats/tickets.py` — win/loss for each category (incl. multi-`Back3` pre-2015
  and exact `FirstPrize`), miss cases, winnings scaling by price, spending
  totals/net, suggestion overlap.
- `web/` (Flask test client) — each `/api/analysis/*` returns a valid Plotly
  figure dict + table; `/api/tickets` POST/GET/DELETE happy + error paths;
  `/api/draw-dates`; `/api/update`; rendered pages contain the DISCLAIMER.
- Regression: the existing 52 tests stay green (pure layers unchanged). Remove
  only the Streamlit-specific dashboard tests, replaced by `web/` tests.
- `ruff` clean.

## Out of scope (later sub-projects)
- Multi-user accounts / auth.
- Pending/future-draw tickets and their later resolution.
- Real-time second–fifth prize tiers and near-first-prize matching (dataset only
  stores `FirstPrize / Last2 / Front3 / Back3`).
- Authentication on the update endpoint / deployment hardening.
