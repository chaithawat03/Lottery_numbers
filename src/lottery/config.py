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
