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


def test_report_uses_real_source_command_and_stable_fingerprint():
    df = add_engineered_features(normalize_columns(generate(400, 60, seed=2)))
    meta = {"labels": {"mode": "embedded"}}
    spec = ExperimentSpec(models=["mlp"], source_kind="file", source_ref="flows.csv")
    first = execute(df, meta, "flows.csv（csv）", spec)
    second = execute(df, meta, "flows.csv（csv）", spec)
    assert "flowlab run flows.csv" in first["experiment"]["command"]
    assert "flowlab demo" not in first["report_md"]
    assert first["experiment_fingerprint"] == second["experiment_fingerprint"]
    assert "逐位一致" not in first["report_md"]
    assert "报告含生成时间，文件字节不保证完全相同" in first["report_md"]
    assert "PR-AUC" in first["report_html"]
    assert 'class="table-scroll"' in first["report_html"]
    assert "验证集最佳" in first["report_html"]
    assert "验证 AUC" in first["report_md"]
    assert "阈值权衡" in first["report_html"]
    assert "测试集只做最终报告" in first["report_md"]


def test_suspicious_badge_follows_verdict():
    from flowlab.report.view import build_view
    from flowlab.service import results_of

    p = _payload()
    meta = {
        "labels": {"mode": "embedded"},
        "verdict": {
            "level": "ok",
            "checks": [
                {"name": "指标可信度", "status": "pass", "detail": "AUC 1.0000，消融已排除端口"}
            ],
        },
    }
    view = build_view(results_of(p), p["warnings"], meta, p["ablation"])
    assert view.suspicious_auc is False
