from __future__ import annotations

import pandas as pd

MIRROR_MAP = {
    "0": "5", "1": "6", "2": "7", "3": "8", "4": "9",
    "5": "0", "6": "1", "7": "2", "8": "3", "9": "4",
}


def position_distribution(series: pd.Series) -> pd.DataFrame:
    s = series.dropna().astype(str)
    width = int(s.map(len).max()) if not s.empty else 0
    data = {f"pos_{p}": [0] * 10 for p in range(width)}
    for value in s:
        for p, digit in enumerate(value):
            data[f"pos_{p}"][int(digit)] += 1
    df = pd.DataFrame(data, index=range(10))
    df.index.name = "digit"
    return df


def _ratio_table(series: pd.Series, predicate, true_label: str, false_label: str) -> pd.DataFrame:
    yes = no = 0
    for value in series.dropna():
        for digit in str(value):
            if predicate(int(digit)):
                yes += 1
            else:
                no += 1
    total = yes + no
    return pd.DataFrame(
        [
            {"kind": true_label, "count": yes, "ratio": yes / total if total else 0.0},
            {"kind": false_label, "count": no, "ratio": no / total if total else 0.0},
        ]
    )


def odd_even_ratio(series: pd.Series) -> pd.DataFrame:
    return _ratio_table(series, lambda d: d % 2 == 1, "odd", "even")


def high_low_ratio(series: pd.Series) -> pd.DataFrame:
    return _ratio_table(series, lambda d: d >= 5, "high", "low")


def mirror_value(number: str) -> str:
    return "".join(MIRROR_MAP[d] for d in number)


def is_ascending(number: str) -> bool:
    return len(number) > 1 and all(
        int(number[i]) < int(number[i + 1]) for i in range(len(number) - 1)
    )


def is_descending(number: str) -> bool:
    return len(number) > 1 and all(
        int(number[i]) > int(number[i + 1]) for i in range(len(number) - 1)
    )
