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
