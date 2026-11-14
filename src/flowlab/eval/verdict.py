"""结果判断：给数字一个"这算正常吗"的答案。

依据来自 docs/CICIDS-复现指南.md 的合理区间（公开论文 + 我们的合成基线）。
原则：
- 只在有依据时给区间，不编造精确阈值；
- 一句话说清"能不能写进论文"，而不是罗列所有可能；
- 判断与泄漏提示必须联动：有泄漏时任何高指标都不给"可信"。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 合理区间（AUC / FPR / 召回）。来源：CICIDS 类数据集上的公开结果范围，
# 只用于发现异常，不是评分标准。
BANDS = {
    "auc": {"low": 0.85, "ok": (0.93, 0.99), "suspicious": 0.995},
    "fpr": {"good_max": 0.08, "suspicious_min": 0.0005},
    "recall": {"low": 0.80, "ok": (0.85, 0.99)},
}


@dataclass
class Verdict:
    level: str  # "ok" | "warn" | "fail"
    headline: str  # 一句话结论
    reasons: list[str] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)  # [{name, status, detail}]

    @property
    def is_ok(self) -> bool:
        return self.level == "ok"


def _fmt(v, digits: int = 4, pct: bool = False) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.2f}%" if pct else f"{v:.{digits}f}"


def judge(
    metrics: dict,
    warns: list[dict],
    n_test: int,
    ablation: dict | None = None,
    used_features: list[str] | None = None,
    split_requested: str | None = None,
    split_effective: str | None = None,
) -> Verdict:
    """返回一句结论 + 可核对的检查项。

    used_features：真正进入特征矩阵的列名。泄漏规则按整张表检查，
    但只有落在 used_features 上的泄漏才会影响结果——`flow_id` 被
    META_COLUMNS 丢掉时，报 id_leak 也不能算阻断。
    """
    auc = metrics.get("auc")
    fpr = metrics.get("fpr")
    recall = metrics.get("recall")

    def _effective(rule_names: set[str]) -> set[str]:
        """只看真正构成威胁的规则（泄漏列确实进了特征）。"""
        present = rule_names & {w["rule"] for w in warns}
        if used_features is None:
            return present
        keep = set()
        for w in warns:
            if w["rule"] not in present:
                continue
            cols = [str(c) for c in w.get("columns", [])]
            if any(c in used_features for c in cols):
                keep.add(w["rule"])
        return keep

    leak_rules = {w["rule"] for w in warns}
    hard_leaks = _effective({"id_leak", "target_leak", "time_leak"})
    has_port_leak = bool(_effective({"port_leak"}))
    # 端口痕迹 + 满分 AUC 同时出现：通常泄漏是主因，升级成 fail。
    # 但如果已经对这一点做过消融、且 Δ 很小，说明端口并没有在抬指标，
    # 这时不该把结论判死——消融就是用来回答"这个泄漏是否真的起作用"的。
    ablated_column = ablation.get("column") if ablation else None
    ablated_delta = None
    if ablation:
        deltas = [r.get("delta") for r in ablation.get("rows", []) if r.get("delta") is not None]
        ablated_delta = max(deltas) if deltas else None
    port_tested_weak = (
        has_port_leak
        and ablated_column == "dst_port"
        and ablated_delta is not None
        and ablated_delta < 0.05
    )
    escalate_port = (
        has_port_leak
        and auc is not None
        and auc >= BANDS["auc"]["suspicious"]
        and not port_tested_weak
    )
    dropped_leaks = leak_rules - hard_leaks - ({"port_leak"} if has_port_leak else set())
    checks: list[dict] = []

    # 0) 切分声明是否兑现
    split_fell_back = (
        split_requested == "temporal"
        and split_effective is not None
        and split_effective != "temporal"
    )
    if split_fell_back:
        checks.append(
            {
                "name": "切分有效性",
                "status": "fail",
                "detail": "请求了时间切分，但实际退化为随机切分；这组结果不能用于时间外推结论",
            }
        )

    # 1) 泄漏
    if hard_leaks:
        checks.append(
            {
                "name": "数据泄漏",
                "status": "fail",
                "detail": "、".join(sorted(hard_leaks)) + " 会把答案带进特征",
            }
        )
    elif escalate_port:
        checks.append(
            {
                "name": "数据泄漏",
                "status": "fail",
                "detail": "端口痕迹与满分 AUC 同时出现，模型学的很可能就是端口",
            }
        )
    elif has_port_leak:
        if port_tested_weak:
            checks.append(
                {
                    "name": "数据泄漏",
                    "status": "pass",
                    "detail": f"端口有痕迹，但消融显示去掉它只掉 {ablated_delta:+.4f}，不影响结论",
                }
            )
        else:
            checks.append(
                {
                    "name": "数据泄漏",
                    "status": "warn",
                    "detail": "端口在某类攻击里高度集中，先跑消融确认",
                }
            )
    elif dropped_leaks:
        checks.append(
            {
                "name": "数据泄漏",
                "status": "pass",
                "detail": "命中的列（"
                + "、".join(sorted(dropped_leaks))
                + "）已在训练前丢弃，不影响结果",
            }
        )
    else:
        checks.append({"name": "数据泄漏", "status": "pass", "detail": "四类规则均未命中"})

    # 2) 指标是否"好得不像真的"
    effective_leak = bool(hard_leaks) or escalate_port
    if auc is not None and auc >= BANDS["auc"]["suspicious"]:
        if effective_leak:
            checks.append(
                {
                    "name": "指标可信度",
                    "status": "fail",
                    "detail": f"AUC {_fmt(auc)} 已达满分区间，先修泄漏再看这个数字",
                }
            )
        elif port_tested_weak:
            checks.append(
                {
                    "name": "指标可信度",
                    "status": "warn",
                    "detail": f"AUC {_fmt(auc)} 满分，但已用消融排除端口；建议换一份数据再确认一次",
                }
            )
        else:
            checks.append(
                {
                    "name": "指标可信度",
                    "status": "warn",
                    "detail": f"AUC {_fmt(auc)} 极高但未发现有效泄漏，建议换一份数据交叉验证",
                }
            )
    elif auc is not None and auc < BANDS["auc"]["low"]:
        checks.append(
            {
                "name": "指标可信度",
                "status": "warn",
                "detail": f"AUC {_fmt(auc)} 低于常见区间 0.93–0.99，先看切分与特征",
            }
        )
    else:
        checks.append(
            {
                "name": "指标可信度",
                "status": "pass",
                "detail": f"AUC {_fmt(auc)}，落在常见区间 0.93–0.99",
            }
        )

    # 3) 误报率能不能用
    if fpr is None:
        checks.append({"name": "误报率", "status": "warn", "detail": "单类数据，无法计算"})
    elif fpr > BANDS["fpr"]["good_max"]:
        checks.append(
            {
                "name": "误报率",
                "status": "warn",
                "detail": f"{_fmt(fpr, pct=True)} 高于 8%，实际部署会淹没告警",
            }
        )
    elif fpr < BANDS["fpr"]["suspicious_min"] and (auc or 0) > 0.99:
        checks.append(
            {
                "name": "误报率",
                "status": "warn",
                "detail": f"{_fmt(fpr, pct=True)} 低得反常，配合高 AUC 先怀疑泄漏",
            }
        )
    else:
        checks.append({"name": "误报率", "status": "pass", "detail": _fmt(fpr, pct=True)})

    # 4) 召回
    if recall is not None:
        if recall < BANDS["recall"]["low"]:
            checks.append(
                {
                    "name": "召回率",
                    "status": "warn",
                    "detail": f"{_fmt(recall)} 低于 0.80，会漏掉大量攻击",
                }
            )
        else:
            checks.append({"name": "召回率", "status": "pass", "detail": _fmt(recall)})

    # 5) 样本量
    if n_test < 50:
        checks.append(
            {"name": "样本量", "status": "fail", "detail": f"测试集仅 {n_test} 条，指标波动极大"}
        )
    elif n_test < 500:
        checks.append(
            {
                "name": "样本量",
                "status": "warn",
                "detail": f"测试集 {n_test} 条，建议 >500 再下结论",
            }
        )
    else:
        checks.append({"name": "样本量", "status": "pass", "detail": f"测试集 {n_test:,} 条"})

    # 6) 消融是否做过
    if ablation:
        deltas = [r.get("delta") for r in ablation.get("rows", []) if r.get("delta") is not None]
        worst = max(deltas) if deltas else None
        col = ablation.get("column")
        if worst is not None and worst > 0.2:
            checks.append(
                {
                    "name": "消融",
                    "status": "fail",
                    "detail": f"去掉 {col} 后 AUC 掉 {worst:+.4f}，模型主要靠这一列",
                }
            )
        elif worst is not None and worst > 0.05:
            checks.append(
                {
                    "name": "消融",
                    "status": "warn",
                    "detail": f"去掉 {col} 后 AUC 掉 {worst:+.4f}，这一列贡献不小",
                }
            )
        else:
            shown = "—" if worst is None else f"{worst:+.4f}"
            checks.append(
                {
                    "name": "消融",
                    "status": "pass",
                    "detail": f"去掉 {col} 影响 {shown}，结论不依赖单一列",
                }
            )
    else:
        checks.append(
            {"name": "消融", "status": "warn", "detail": "还没跑过，无法确认是否依赖单一列"}
        )

    fails = [c for c in checks if c["status"] == "fail"]
    warns_n = [c for c in checks if c["status"] == "warn"]

    if fails:
        level = "fail"
        # 头条只点最该先修的那一件，不重复明细里的原句
        names = {c["name"] for c in fails}
        if "切分有效性" in names:
            headline = "这组结果还不能写进论文：时间切分未生效，已退化为随机切分"
        elif "消融" in names:
            headline = "这组结果还不能写进论文：指标主要来自单一列，去掉就垮"
        elif "样本量" in names:
            headline = "这组结果还不能写进论文：样本太少，指标不可信"
        elif "数据泄漏" in names:
            headline = "这组结果还不能写进论文：数据泄漏没修，指标不能作为结论"
        else:
            headline = "这组结果还不能写进论文：指标超出可信范围"
        lead = next(c for c in fails if c["name"] != "数据泄漏") if len(fails) > 1 else fails[0]
        reasons = [c["detail"] for c in fails + warns_n if c is not lead][:3]
    elif warns_n:
        level = "warn"
        headline = "可以用，但需要说明：" + warns_n[0]["detail"]
        reasons = [c["detail"] for c in warns_n][:3]
    else:
        level = "ok"
        headline = "未发现阻断性问题：无有效泄漏、指标在常见区间、样本量足够；仍需结合实际场景复核"
        reasons = []

    return Verdict(level=level, headline=headline, reasons=reasons, checks=checks)
