import pytest

from flowlab.engineer import add_engineered_features
from flowlab.schema import normalize_columns
from flowlab.service import ExperimentSpec, demo_frame, execute
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
