from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from lottery.data.models import ALL_COLUMNS, INT_COLUMNS, NUMBER_COLUMNS, TABLE_NAME

logger = logging.getLogger(__name__)


class DrawRepository:
    def __init__(self, db_path: Path | str, csv_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path)
        self.csv_path = Path(csv_path) if csv_path else None

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
