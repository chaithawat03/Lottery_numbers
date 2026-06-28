import pandas as pd

from lottery.dashboard.components.charts import (
    frequency_bar,
    heatmap_10x10,
    transition_heatmap,
)


def test_frequency_bar_builds_figure():
    freq = pd.DataFrame({"value": ["01", "02"], "count": [2, 1]})
    fig = frequency_bar(freq, "t")
    assert len(fig.data) == 1


def test_heatmap_10x10_shape():
    freq = pd.DataFrame({"value": ["00", "99"], "count": [3, 5]})
    fig = heatmap_10x10(freq, "t")
    z = fig.data[0].z
    assert len(z) == 10 and len(z[0]) == 10
    assert z[0][0] == 3
    assert z[9][9] == 5


def test_transition_heatmap_builds():
    matrix = pd.DataFrame([[0.5, 0.5], [1.0, 0.0]], index=[0, 1], columns=[0, 1])
    fig = transition_heatmap(matrix, "t")
    assert fig.data[0].z is not None
