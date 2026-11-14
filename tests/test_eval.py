import numpy as np
import pytest

from flowlab.eval.metrics import (
    choose_threshold_f1,
    choose_threshold_fpr,
    curve_data,
    threshold_scan,
)
from flowlab.eval.runner import EvalResult, dataset_hash, run_experiment, select_best
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
    assert a[0].params["seed"] == 7


def test_three_way_counts_are_complete():
    df = _df()
    res, _ = run_experiment(df, models=["mlp"], split="temporal")
    result = res[0]
    assert result.n_train + result.n_validation + result.n_test == len(df)
    assert result.validation_metrics["support"] == result.n_validation
    assert result.metrics["support"] == result.n_test


def test_model_selection_uses_validation_not_test_auc():
    overfit = EvalResult(
        model="overfit",
        kind="supervised",
        metrics={"auc": 0.99},
        validation_metrics={"auc": 0.71},
        confusion={},
        duration_s=0,
    )
    stable = EvalResult(
        model="stable",
        kind="supervised",
        metrics={"auc": 0.91},
        validation_metrics={"auc": 0.93},
        confusion={},
        duration_s=0,
    )
    assert select_best([overfit, stable]).model == "stable"


def test_auto_threshold_is_selected_from_validation_scores():
    y = [0, 0, 0, 1, 1, 1]
    scores = [0.05, 0.1, 0.3, 0.45, 0.7, 0.9]
    selected = choose_threshold_f1(y, scores)
    assert 0 < selected <= 1
    assert selected > 0.3


def test_target_fpr_threshold_keeps_validation_false_positive_rate_bounded():
    y = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    scores = np.array([0.05, 0.15, 0.25, 0.35, 0.55, 0.45, 0.6, 0.7, 0.8, 0.9])
    selected = choose_threshold_fpr(y, scores, target_fpr=0.2)
    assert (scores[y == 0] >= selected).mean() <= 0.2
    assert (scores[y == 1] >= selected).mean() == 1


def test_threshold_scan_has_eleven_deployment_points():
    rows = threshold_scan([0, 0, 1, 1], [0.1, 0.4, 0.6, 0.9])
    assert len(rows) == 11
    assert rows[0]["threshold"] == 0.05
    assert rows[-1]["threshold"] == 0.95


def test_curve_data_is_bounded_and_supervised_calibration_has_brier():
    y_true = np.array([0] * 80 + [1] * 20)
    scores = np.linspace(0.01, 0.99, len(y_true))
    curves = curve_data(y_true, scores, supervised=True, points=24)
    assert 2 <= len(curves["roc_curve"]) <= 24
    assert 2 <= len(curves["pr_curve"]) <= 24
    assert curves["roc_curve"][0]["fpr"] == 0
    assert curves["roc_curve"][-1]["tpr"] == 1
    assert curves["calibration"]
    assert curves["brier_score"] is not None
    assert "监督模型" in curves["calibration_note"]


def test_curve_data_marks_unsupervised_scores_as_non_probability():
    curves = curve_data([0, 0, 1, 1], [0.1, 0.4, 0.6, 0.9], supervised=False)
    assert curves["roc_curve"] and curves["pr_curve"]
    assert curves["calibration"] == []
    assert curves["brier_score"] is None
    assert "不是概率" in curves["calibration_note"]


def test_auto_threshold_mode_records_source():
    res, _ = run_experiment(
        _df(),
        models=["mlp"],
        split="temporal",
        threshold_mode="f1",
    )
    assert res[0].threshold_source == "validation_f1"
    assert 0 <= res[0].threshold <= 1
    assert len(res[0].threshold_scan) == 11


def test_target_fpr_mode_records_target_and_validation_source():
    res, _ = run_experiment(
        _df(),
        models=["mlp"],
        split="temporal",
        threshold_mode="fpr",
        target_fpr=0.05,
    )
    assert res[0].threshold_source == "validation_fpr"
    assert res[0].threshold_target_fpr == 0.05
    assert res[0].validation_metrics["fpr"] <= 0.05


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
