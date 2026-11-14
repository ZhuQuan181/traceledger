import pytest

from flowlab.eval.runner import dataset_hash, run_experiment
from flowlab.schema import normalize_columns
from flowlab.synthetic import generate


def _df():
    return normalize_columns(generate(n_normal=600, n_attack=100, seed=21))


def test_mlp_learns_synthetic_data():
    res, warns = run_experiment(_df(), models=["mlp"], split="temporal")
    assert len(res) == 1
    assert res[0].metrics["auc"] and res[0].metrics["auc"] > 0.9
    assert warns


def test_reproducible_same_seed():
    a, _ = run_experiment(_df(), models=["mlp"], seed=7)
    b, _ = run_experiment(_df(), models=["mlp"], seed=7)
    assert a[0].metrics == b[0].metrics
    assert a[0].dataset_hash == b[0].dataset_hash


def test_hash_changes_with_data():
    df = _df()
    h1 = dataset_hash(df)
    df2 = df.copy()
    df2.loc[df2.index[0], "dst_port"] = 9999
    assert dataset_hash(df2) != h1


def test_explain_builds_investigation_views():
    res, _ = run_experiment(_df(), models=["mlp"], split="temporal", explain=True)
    result = res[0]
    assert result.by_label
    assert sum(row["total"] for row in result.by_label) == result.n_test
    assert any(row["kind"] == "attack" for row in result.by_label)
    assert any(row["kind"] == "benign" for row in result.by_label)
    assert result.source_ranking
    assert result.source_ranking[0]["alerts"] >= result.source_ranking[0]["true_attacks"]


def test_missing_labels_are_rejected_instead_of_treated_as_attacks():
    df = _df()
    df.loc[df.index[0], "label"] = None
    with pytest.raises(ValueError, match="不能.*当作攻击"):
        run_experiment(df, models=["mlp"])


def test_unknown_and_empty_model_lists_are_rejected():
    with pytest.raises(ValueError, match="未知模型"):
        run_experiment(_df(), models=["does-not-exist"])
    with pytest.raises(ValueError, match="至少选择一个模型"):
        run_experiment(_df(), models=[])


def test_test_split_must_contain_both_classes():
    df = _df()
    df["label"] = "BENIGN"
    with pytest.raises(ValueError, match="同时包含 BENIGN 和攻击样本"):
        run_experiment(df, models=["iforest"])

    df["label"] = "ATTACK"
    with pytest.raises(ValueError, match="同时包含 BENIGN 和攻击样本"):
        run_experiment(df, models=["iforest"])
