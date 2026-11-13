from flowlab.eval.checklist import build_checklist, checklist_summary


def _ds(**kw):
    base = {"split": "temporal", "test": 1600, "attack_test": 150,
            "hash": "abc123", "seed": 42, "labels": {"mode": "embedded"},
            "features": {"used": ["dst_port", "bytes_per_s", "fwd_packets"], "encoded": 5}}
    base.update(kw)
    return base


def _leak(rule):
    return {"rule": rule, "columns": ["dst_port"]}


def test_all_pass_with_ablation():
    items = build_checklist(_ds(), [], {"column": "dst_port", "rows": []})
    passed, total = checklist_summary(items)
    assert passed == total, [i for i in items if not i["ok"]]


def test_random_split_fails_item():
    items = build_checklist(_ds(split="random"), [], {"column": "dst_port", "rows": []})
    item = next(i for i in items if i["item"] == "按时间切分")
    assert item["ok"] is False
    assert "未来" in item["detail"]


def test_missing_ablation_fails_item():
    items = build_checklist(_ds(), [], None)
    item = next(i for i in items if i["item"] == "做过消融")
    assert item["ok"] is False


def test_small_test_set_fails():
    items = build_checklist(_ds(test=80, attack_test=5), [], {"column": "x", "rows": []})
    item = next(i for i in items if i["item"] == "测试集样本量足够")
    assert item["ok"] is False


def test_hard_leak_blocks():
    items = build_checklist(_ds(), [_leak("target_leak")], {"column": "x", "rows": []})
    item = next(i for i in items if i["item"] == "硬泄漏已排除")
    assert item["ok"] is False


def test_unresolved_leak_blocks_even_if_not_hard():
    """端口泄漏把结论判成不可用时，清单不能显示全部通过。"""
    items = build_checklist(_ds(), [_leak("port_leak")], {"column": "dst_port", "rows": []},
                            unresolved_leak=True)
    item = next(i for i in items if i["item"] == "硬泄漏已排除")
    assert item["ok"] is False
    assert "port_leak" in item["detail"]
    passed, total = checklist_summary(items)
    assert passed < total


def test_port_leak_without_escalation_passes():
    """端口泄漏没升级成 fail 时，清单这一项算通过（由 verdict 决定是否升级）。"""
    items = build_checklist(_ds(), [_leak("port_leak")], {"column": "dst_port", "rows": []},
                            unresolved_leak=False)
    item = next(i for i in items if i["item"] == "硬泄漏已排除")
    assert item["ok"] is True


def test_row_order_labels_flagged():
    items = build_checklist(_ds(labels={"mode": "row_order"}), [], {"column": "x", "rows": []})
    item = next(i for i in items if i["item"] == "披露标签来源")
    assert item["ok"] is False
    assert "精确度" in item["detail"]


def test_missing_hash_fails():
    items = build_checklist(_ds(hash=""), [], {"column": "x", "rows": []})
    item = next(i for i in items if i["item"] == "记录数据指纹与随机种子")
    assert item["ok"] is False
