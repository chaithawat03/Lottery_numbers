from __future__ import annotations

TABLE_NAME = "draws"

NUMBER_COLUMNS = [
    "FirstPrize",
    "Last2",
    "Front3_1",
    "Front3_2",
    "Back3_1",
    "Back3_2",
    "Back3_3",
    "Back3_4",
]
INT_COLUMNS = ["Year", "Month"]
ALL_COLUMNS = ["DrawDate", *INT_COLUMNS, *NUMBER_COLUMNS]
