import pandas as pd

from flowlab.schema import normalize_columns
from flowlab.synthetic import generate
from flowlab.eval.split import split_indices


def _df():
    return normalize_columns(generate(n_normal=300, n_attack=60, seed=9))


def test_temporal_split_is_ordered():
    df = _df()
    tr, te = split_indices(df, mode="temporal", test_size=0.3)
    ts = pd.to_datetime(df["timestamp"])
    assert ts.loc[tr].max() <= ts.loc[te].min()
    assert len(tr) + len(te) == len(df)


def test_random_split_deterministic():
    df = _df()
    a = split_indices(df, mode="random", seed=1)
    b = split_indices(df, mode="random", seed=1)
    assert list(a[0]) == list(b[0])
