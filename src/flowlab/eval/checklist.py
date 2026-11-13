"""投稿前自查清单：5 条能当场回答的 yes/no。

和 `verdict.judge()` 的分工：
- judge：**自动**判断这批结果能不能用（基于指标与泄漏）
- checklist：**人工**核对流程是否规范（切分、种子、指纹、样本量、消融）

两者都要通过，结论才真的站得住。清单进报告，方便投稿时逐条打勾。
"""
from __future__ import annotations


def build_checklist(dataset: dict, warnings: list[dict], ablation: dict | None,
                    unresolved_leak: bool = False) -> list[dict]:
    """返回 [{item, ok, detail}]，ok=False 的项需要人工补。

    unresolved_leak：由 `verdict.judge()` 判定"泄漏没修"时传 True。
    清单不能只看 id/target/time——端口痕迹配上满分 AUC 也会让结论不可用，
    否则会出现"结论卡说不可用、清单说全部通过"的自相矛盾。
    """
    split = dataset.get("split")
    test = int(dataset.get("test") or 0)
    attack_test = int(dataset.get("attack_test") or 0)
    labels_mode = (dataset.get("labels") or {}).get("mode")
    features = (dataset.get("features") or {}).get("used") or []
    hard = {"id_leak", "target_leak", "time_leak"}
    rules = {w["rule"] for w in warnings}

    items: list[dict] = []

    items.append({
        "item": "按时间切分",
        "ok": split == "temporal",
        "detail": "时间切分" if split == "temporal"
                  else "用了随机切分：若数据带时间戳，测试集的『未来』会进训练集",
    })

    items.append({
        "item": "记录数据指纹与随机种子",
        "ok": bool(dataset.get("hash")) and dataset.get("seed") is not None,
        "detail": f"指纹 {dataset.get('hash', '—')} · 种子 {dataset.get('seed', '—')}",
    })

    items.append({
        "item": "披露标签来源",
        "ok": labels_mode in {"embedded", "flow_id"} or labels_mode is None,
        "detail": f"标签对齐方式：{labels_mode or 'embedded'}"
                  + ("（五元组/行序对齐，精确度低于 flow_id）"
                     if labels_mode in {"row_order"} or str(labels_mode or "").startswith("src_ip") else ""),
    })

    if hard & rules:
        leak_ok, leak_detail = False, "命中 " + "、".join(sorted(hard & rules)) + "，修完再投稿"
    elif unresolved_leak:
        leak_ok = False
        hint = "、".join(sorted(rules)) or "泄漏"
        leak_detail = f"仍有未修的泄漏（{hint}）在抬高指标，先跑消融或去掉该列"
    else:
        leak_ok, leak_detail = True, "未命中 id/target/time 泄漏"
    items.append({"item": "硬泄漏已排除", "ok": leak_ok, "detail": leak_detail})

    items.append({
        "item": "测试集样本量足够",
        "ok": test >= 500 and attack_test >= 20,
        "detail": f"测试集 {test:,} 条 / 攻击 {attack_test:,} 条"
                  + ("" if test >= 500 and attack_test >= 20 else "（建议 ≥500 条且攻击 ≥20 条）"),
    })

    items.append({
        "item": "做过消融",
        "ok": ablation is not None,
        "detail": (f"已消融 {ablation.get('column')}" if ablation
                   else "未做：无法证明结论不依赖单一列"),
    })

    items.append({
        "item": "特征清单已记录",
        "ok": len(features) >= 3,
        "detail": f"{len(features)} 列参与训练" if features else "无特征记录",
    })

    return items


def checklist_summary(items: list[dict]) -> tuple[int, int]:
    passed = sum(1 for i in items if i["ok"])
    return passed, len(items)
