from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def frequency_bar(freq: pd.DataFrame, title: str) -> go.Figure:
    return px.bar(freq, x="value", y="count", title=title)


def heatmap_10x10(freq: pd.DataFrame, title: str) -> go.Figure:
    grid = [[0] * 10 for _ in range(10)]
    for _, row in freq.iterrows():
        value = str(row["value"]).zfill(2)
        grid[int(value[0])][int(value[1])] = row["count"]
    return go.Figure(
        data=go.Heatmap(z=grid, x=list(range(10)), y=list(range(10))),
        layout=go.Layout(title=title),
    )


def transition_heatmap(matrix: pd.DataFrame, title: str) -> go.Figure:
    return go.Figure(
        data=go.Heatmap(z=matrix.to_numpy(), x=list(matrix.columns), y=list(matrix.index)),
        layout=go.Layout(title=title),
    )


def suggestion_bar(df: pd.DataFrame, title: str) -> go.Figure:
    return px.bar(df, x="value", y="score", title=title)
