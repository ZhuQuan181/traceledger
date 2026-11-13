from flowlab.engineer import add_engineered_features
from flowlab.schema import normalize_columns
from flowlab.service import ExperimentSpec, execute
from flowlab.synthetic import generate


def test_execute_returns_complete_payload():
    df = add_engineered_features(normalize_columns(generate(600, 80, seed=3)))
    payload = execute(df, {"labels": {"mode": "embedded"}}, "test", ExperimentSpec(models=["mlp"]))
    for key in ("dataset", "warnings", "results", "report_md", "report_html", "best_model"):
        assert key in payload
    assert payload["dataset"]["rows"] == 680
    assert "<html" in payload["report_html"]
