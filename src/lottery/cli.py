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
