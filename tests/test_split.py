import pandas as pd

from flowlab.eval.split import plan_split, split_indices
from flowlab.schema import normalize_columns
from flowlab.synthetic import generate


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


def test_temporal_fallback_is_explicit():
    df = _df().drop(columns=["timestamp"])
    plan = plan_split(df, mode="temporal", seed=3)
    assert plan.requested == "temporal"
    assert plan.effective == "random"
    assert plan.fell_back is True
    assert any("退化" in message for message in plan.warnings)


def test_benign_aliases_are_recognized_in_coverage_warnings():
    df = _df().drop(columns=["timestamp"])
    df["label"] = df["label"].replace({"BENIGN": "normal"})
    plan = plan_split(df, mode="random", seed=3)
    assert plan.warnings == []
