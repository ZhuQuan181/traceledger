import pandas as pd
import pytest

from flowlab.eval.split import _entity_series, _split_diagnostics, plan_split, split_indices
from flowlab.schema import normalize_columns
from flowlab.synthetic import generate


def _df():
    return normalize_columns(generate(n_normal=300, n_attack=60, seed=9))


def test_temporal_split_is_ordered():
    df = _df()
    plan = plan_split(df, mode="temporal", test_size=0.3, validation_size=0.2)
    ts = pd.to_datetime(df["timestamp"])
    assert ts.loc[plan.train].max() <= ts.loc[plan.validation].min()
    assert ts.loc[plan.validation].max() <= ts.loc[plan.test].min()
    assert len(plan.train) + len(plan.validation) + len(plan.test) == len(df)
    assert not set(plan.train) & set(plan.validation)
    assert not set(plan.train) & set(plan.test)
    assert not set(plan.validation) & set(plan.test)


def test_random_split_deterministic():
    df = _df()
    a = plan_split(df, mode="random", seed=1)
    b = plan_split(df, mode="random", seed=1)
    assert list(a.train) == list(b.train)
    assert list(a.validation) == list(b.validation)
    assert list(a.test) == list(b.test)


def test_legacy_two_way_split_keeps_all_rows():
    df = _df()
    train, test = split_indices(df, mode="temporal", test_size=0.3)
    assert len(train) + len(test) == len(df)
    assert not set(train) & set(test)
    ts = pd.to_datetime(df["timestamp"])
    assert ts.loc[train].max() <= ts.loc[test].min()


def test_three_way_split_rejects_too_large_holdout():
    with pytest.raises(ValueError, match="不能超过 0.8"):
        plan_split(_df(), test_size=0.5, validation_size=0.4)


def test_group_split_keeps_entities_in_one_subset():
    df = _df()
    plan = plan_split(df, mode="group", test_size=0.3, validation_size=0.2)
    entities, _ = _entity_series(df)
    assert not set(entities.loc[plan.train]) & set(entities.loc[plan.validation])
    assert not set(entities.loc[plan.train]) & set(entities.loc[plan.test])
    assert not set(entities.loc[plan.validation]) & set(entities.loc[plan.test])
    assert plan.diagnostics["group_key"]


def test_duplicate_diagnostics_finds_cross_split_rows():
    df = pd.DataFrame({"x": [1, 1, 1, 2], "label": ["BENIGN"] * 4})
    diagnostics, messages = _split_diagnostics(
        df,
        pd.Index([0]),
        pd.Index([1]),
        pd.Index([2, 3]),
    )
    assert diagnostics["duplicate_cross"]["train_validation"] == 1
    assert diagnostics["duplicate_cross"]["train_test"] == 1
    assert any("完全重复" in message for message in messages)


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
