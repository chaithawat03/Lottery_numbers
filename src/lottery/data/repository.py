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
