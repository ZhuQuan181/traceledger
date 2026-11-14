from flowlab.eval.verdict import judge


def _m(auc=0.96, fpr=0.03, recall=0.92):
    return {"auc": auc, "fpr": fpr, "recall": recall}


def _leak(rule, cols):
    return {"rule": rule, "columns": cols, "severity": "high", "message": "", "suggestion": ""}


def test_clean_result_is_ok():
    v = judge(_m(), [], n_test=2000)
    assert v.level in {"ok", "warn"}  # 消融没跑 -> warn
    assert "消融" in [c["name"] for c in v.checks if c["status"] == "warn"]


def test_clean_with_ablation_is_ok():
    v = judge(_m(), [], n_test=2000, ablation={"column": "dst_port", "rows": [{"delta": 0.01}]})
    assert v.level == "ok"
    assert "未发现阻断性问题" in v.headline
    assert "结合实际场景复核" in v.headline


def test_id_leak_on_dropped_column_does_not_block():
    """flow_id 被丢掉时，id_leak 不该阻断结论。"""
    warns = [_leak("id_leak", ["flow_id"])]
    v = judge(
        _m(),
        warns,
        n_test=2000,
        ablation={"column": "dst_port", "rows": [{"delta": 0.0}]},
        used_features=["dst_port", "bytes_per_s"],
    )
    leak = next(c for c in v.checks if c["name"] == "数据泄漏")
    assert leak["status"] == "pass"
    assert "已在训练前丢弃" in leak["detail"]
    assert v.level == "ok"


def test_id_leak_on_used_column_blocks():
    warns = [_leak("id_leak", ["flow_id"])]
    v = judge(_m(), warns, n_test=2000, used_features=["flow_id", "dst_port"])
    leak = next(c for c in v.checks if c["name"] == "数据泄漏")
    assert leak["status"] == "fail"


def test_perfect_auc_with_leak_fails():
    warns = [_leak("port_leak", ["dst_port"])]
    v = judge(
        {"auc": 1.0, "fpr": 0.0, "recall": 1.0}, warns, n_test=2000, used_features=["dst_port"]
    )
    assert v.level == "fail"
    assert "不能作为结论" in v.headline


def test_perfect_auc_without_leak_warns():
    v = judge(
        {"auc": 0.999, "fpr": 0.02, "recall": 0.99},
        [],
        n_test=2000,
        ablation={"column": "dst_port", "rows": [{"delta": 0.0}]},
    )
    assert v.level == "warn"
    assert "交叉验证" in next(c["detail"] for c in v.checks if c["name"] == "指标可信度")


def test_low_auc_warns():
    v = judge({"auc": 0.70, "fpr": 0.05, "recall": 0.60}, [], n_test=2000)
    assert any(c["status"] == "warn" for c in v.checks if c["name"] == "指标可信度")


def test_high_fpr_warns():
    v = judge({"auc": 0.96, "fpr": 0.25, "recall": 0.9}, [], n_test=2000)
    assert "淹没告警" in next(c["detail"] for c in v.checks if c["name"] == "误报率")


def test_tiny_test_set_fails():
    v = judge(_m(), [], n_test=20)
    assert v.level == "fail"
    assert "样本太少" in v.headline


def test_ablation_heavy_drop_is_lead_reason():
    v = judge(_m(), [], n_test=2000, ablation={"column": "dst_port", "rows": [{"delta": 0.35}]})
    assert v.level == "fail"
    assert "单一列" in v.headline


def test_port_leak_escalates_with_perfect_auc():
    """端口泄漏 + 满分 AUC，且没做过消融：必须升级为 fail。"""
    warns = [_leak("port_leak", ["dst_port"])]
    v = judge(
        {"auc": 1.0, "fpr": 0.0, "recall": 1.0}, warns, n_test=2000, used_features=["dst_port"]
    )
    leak = next(c for c in v.checks if c["name"] == "数据泄漏")
    assert leak["status"] == "fail"
    assert v.level == "fail"


def test_ablation_can_clear_port_leak():
    """消融证明端口只影响一点点时，不能把结论判死。"""
    warns = [_leak("port_leak", ["dst_port"])]
    v = judge(
        {"auc": 1.0, "fpr": 0.001, "recall": 1.0},
        warns,
        n_test=2000,
        ablation={"column": "dst_port", "rows": [{"model": "mlp", "delta": 0.0093}]},
        used_features=["dst_port"],
    )
    leak = next(c for c in v.checks if c["name"] == "数据泄漏")
    assert leak["status"] == "pass"
    assert "不影响结论" in leak["detail"]
    assert v.level != "fail"


def test_ablation_heavy_drop_still_fails():
    """消融掉得很多时，仍然判不可用。"""
    warns = [_leak("port_leak", ["dst_port"])]
    v = judge(
        {"auc": 0.99, "fpr": 0.02, "recall": 0.97},
        warns,
        n_test=2000,
        ablation={"column": "dst_port", "rows": [{"delta": 0.4}]},
        used_features=["dst_port"],
    )
    assert v.level == "fail"
    assert "单一列" in v.headline


def test_missing_fpr_is_warn_not_crash():
    v = judge({"auc": 0.95, "fpr": None, "recall": 0.9}, [], n_test=1000)
    fpr_check = next(c for c in v.checks if c["name"] == "误报率")
    assert fpr_check["status"] == "warn"


def test_temporal_fallback_blocks_temporal_claim():
    v = judge(
        _m(),
        [],
        n_test=2000,
        ablation={"column": "dst_port", "rows": [{"delta": 0.01}]},
        split_requested="temporal",
        split_effective="random",
    )
    check = next(c for c in v.checks if c["name"] == "切分有效性")
    assert check["status"] == "fail"
    assert v.level == "fail"
