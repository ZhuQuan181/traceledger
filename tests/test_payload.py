from flowlab.engineer import add_engineered_features
from flowlab.schema import normalize_columns
from flowlab.service import ExperimentSpec, execute
from flowlab.synthetic import generate


def _payload(n_normal=400, n_attack=60):
    df = add_engineered_features(normalize_columns(generate(n_normal, n_attack, seed=2)))
    return execute(df, {"labels": {"mode": "embedded"}}, "test", ExperimentSpec(models=["mlp"]))


def test_class_distribution_sums_to_rows():
    p = _payload()
    classes = p["dataset"]["classes"]
    assert classes and sum(c["count"] for c in classes) == p["dataset"]["rows"]
    labels = {c["label"]: c["count"] for c in classes}
    assert labels["BENIGN"] == 400 and labels["DDoS"] == 60


def test_features_recorded():
    p = _payload()
    used = p["dataset"]["features"]["used"]
    assert len(used) >= 10
    assert p["dataset"]["features"]["encoded"] >= len(used)
    assert "dst_port" in used


def test_reports_mention_classes_and_features():
    p = _payload()
    assert "类别分布" in p["report_md"]
    assert "参与训练的特征" in p["report_md"]
    assert "类别分布" in p["report_html"]
    assert 'class="feat"' in p["report_html"]
