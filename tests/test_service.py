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
