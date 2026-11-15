import pytest

from flowlab.engineer import add_engineered_features
from flowlab.eval.ablation import ablate
from flowlab.eval.runner import EvalResult
from flowlab.schema import normalize_columns
from flowlab.service import ExperimentSpec, demo_frame, execute, score_payload
from flowlab.synthetic import generate


def test_execute_returns_complete_payload():
    df = add_engineered_features(normalize_columns(generate(600, 80, seed=3)))
    payload = execute(df, {"labels": {"mode": "embedded"}}, "test", ExperimentSpec(models=["mlp"]))
    for key in ("dataset", "warnings", "results", "report_md", "report_html", "best_model"):
        assert key in payload
    assert payload["dataset"]["rows"] == 680
    assert "<html" in payload["report_html"]


def test_default_demo_has_no_port_leak_warning():
    df, meta, source = demo_frame(400, 80, seed=42)
    payload = execute(df, meta, source, ExperimentSpec(models=["mlp"]))
    assert all(w["rule"] != "port_leak" for w in payload["warnings"])


def test_ablation_must_target_a_feature_used_by_the_model():
    df = add_engineered_features(normalize_columns(generate(300, 50, seed=3)))
    with pytest.raises(ValueError, match="没有参与训练"):
        execute(
            df,
            {"labels": {"mode": "embedded"}},
            "test",
            ExperimentSpec(models=["mlp"], ablate="label"),
        )


def test_duplicate_models_are_run_once():
    df = add_engineered_features(normalize_columns(generate(300, 50, seed=3)))
    payload = execute(
        df,
        {"labels": {"mode": "embedded"}},
        "test",
        ExperimentSpec(models=["mlp", "mlp"]),
    )
    assert [row["model"] for row in payload["results"]] == ["mlp"]


def test_invalid_target_fpr_is_rejected_before_training():
    df = add_engineered_features(normalize_columns(generate(300, 50, seed=3)))
    with pytest.raises(ValueError, match="target_fpr"):
        execute(
            df,
            {"labels": {"mode": "embedded"}},
            "test",
            ExperimentSpec(models=["mlp"], threshold_mode="fpr", target_fpr=0),
        )


def test_ablation_reuses_the_baseline_instead_of_training_it_twice(monkeypatch):
    import flowlab.eval.ablation as ablation_module

    df = add_engineered_features(normalize_columns(generate(200, 40, seed=3)))
    baseline = [
        EvalResult(
            model="mlp",
            kind="supervised",
            metrics={"auc": 0.9},
            confusion={},
            duration_s=0.01,
        )
    ]
    calls = []

    def fake_run(frame, **kwargs):
        calls.append(frame)
        return baseline, []

    monkeypatch.setattr(ablation_module, "run_experiment", fake_run)
    result = ablate(
        df,
        "dst_port",
        base_results=baseline,
        models=["mlp"],
        split="temporal",
    )
    assert len(calls) == 1
    assert "dst_port" not in calls[0].columns
    assert result.with_column is baseline


def test_unlabeled_scoring_ranks_flows_without_inventing_metrics():
    df = add_engineered_features(normalize_columns(generate(500, 60, seed=4))).drop(
        columns=["label"]
    )
    payload = score_payload(df, {"format": {"format": "synthetic"}}, "unlabeled", top=12)
    assert payload["mode"] == "score"
    assert payload["dataset"]["rows"] == 560
    assert payload["summary"]["returned"] == 12
    assert len(payload["top"]) == 12
    assert [row["score"] for row in payload["top"]] == sorted(
        (row["score"] for row in payload["top"]), reverse=True
    )
    assert "results" not in payload
    assert "AUC" in payload["note"]


def test_unlabeled_scoring_rejects_supervised_models():
    df = add_engineered_features(normalize_columns(generate(200, 30, seed=4))).drop(
        columns=["label"]
    )
    with pytest.raises(ValueError, match="只能使用无监督模型"):
        score_payload(df, {}, "unlabeled", model="mlp")
