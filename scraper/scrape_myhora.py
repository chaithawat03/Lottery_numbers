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
