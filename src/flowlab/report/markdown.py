"""Markdown 报告：只做排版，所有数值来自 ReportView。"""
from __future__ import annotations

from datetime import datetime

from flowlab.eval.runner import EvalResult
from flowlab.report.view import ReportView, build_view


def _meta_table(v: ReportView) -> str:
    rows = [
        ("数据来源", f"{v.source}（{v.fmt}）"),
        ("样本量", f"{v.rows}（训练 {v.train} / 测试 {v.test}）"),
        ("攻击样本", f"训练 {v.attack_train} / 测试 {v.attack_test}"),
        ("数据指纹", f"`{v.hash}`"),
        ("切分方式", v.split),
        ("随机种子", str(v.seed)),
        ("判定阈值", v.threshold),
        ("标签对齐", f"{v.labels_mode}（{v.labels_labelled}/{v.labels_total}）" if v.labels_total else v.labels_mode),
        ("速率兜底", f"{v.min_duration_ms} ms"),
    ]
    return "| 项 | 值 |\n|---|---|\n" + "\n".join(f"| {k} | {val} |" for k, val in rows)


def _classes_line(v: ReportView) -> str:
    if not v.classes:
        return ""
    parts = [f"{c['label']} {c['count']:,}" for c in v.classes]
    return "\n**类别分布**：" + " · ".join(parts) + "\n"


def _features_line(v: ReportView) -> str:
    if not v.features:
        return ""
    shown = ", ".join(f"`{f}`" for f in v.features)
    return (f"\n**参与训练的特征**：{len(v.features)} 列（编码后 {v.encoded_features} 维）\n\n"
            f"{shown}\n")


def _warn_table(warns: list[dict]) -> str:
    if not warns:
        return "未检测到明显的数据泄漏。\n"
    out = ["| 严重度 | 规则 | 涉及列 | 说明 | 建议 |", "|---|---|---|---|---|"]
    for w in warns:
        out.append(f"| {w['severity']} | `{w['rule']}` | {', '.join(map(str, w['columns']))} | "
                   f"{w['message']} | {w['suggestion']} |")
    return "\n".join(out) + "\n"


def _model_table(v: ReportView) -> str:
    head = "| 模型 | 类型 | AUC | F1 | 精确率 | 召回率 | 误报率 | 耗时 | TP | FP | FN | TN |"
    sep = "|---|---|---|---|---|---|---|---|---|---|---|---|"
    rows = [
        f"| {m.model}{' 🏆' if m.is_best else ''} | {m.kind_cn} | {m.auc} | {m.f1} | {m.precision} | "
        f"{m.recall} | {m.fpr} | {m.duration} | {m.tp} | {m.fp} | {m.fn} | {m.tn} |"
        for m in v.models
    ]
    return "\n".join([head, sep, *rows])


def _ablation_block(v: ReportView) -> str:
    if not v.ablation:
        return ""
    rows = ["| 模型 | AUC（含该列） | AUC（去掉后） | Δ |", "|---|---|---|---|"]
    for r in v.ablation.get("rows", []):
        aw = "—" if r.get("auc_with") is None else f"{r['auc_with']:.4f}"
        ao = "—" if r.get("auc_without") is None else f"{r['auc_without']:.4f}"
        d = "—" if r.get("delta") is None else f"{r['delta']:+.4f}"
        rows.append(f"| {r['model']} | {aw} | {ao} | {d} |")
    return ("## 05. 消融：去掉 `" + str(v.ablation.get("column")) + "`\n\n"
            + "\n".join(rows) + f"\n\n> {v.ablation.get('note', '')}\n\n")


def _verdict_block(v: ReportView) -> str:
    """结论区块：放最前面，回答"这组数字能不能用"。"""
    vd = v.verdict or {}
    if not vd:
        return ""
    icon = {"ok": "✅", "warn": "⚠️", "fail": "⛔"}.get(vd.get("level", ""), "•")
    out = [f"## 0. 结论", "", f"### {icon} {vd.get('headline', '')}", ""]
    checks = vd.get("checks") or []
    if checks:
        out += ["| 检查项 | 结果 | 说明 |", "|---|---|---|"]
        mark = {"pass": "通过", "warn": "注意", "fail": "不通过"}
        for c in checks:
            out.append(f"| {c['name']} | {mark.get(c['status'], c['status'])} | {c['detail']} |")
        out.append("")
    reasons = vd.get("reasons") or []
    if reasons:
        shown = {c["detail"] for c in checks}
        extra = [r for r in reasons if r not in shown]
        if extra:
            out += ["> 另需注意：" + "；".join(extra), ""]
    out += ["> 判断依据：CICIDS 类数据集上的常见区间（AUC 0.93–0.99、误报率 0.5%–8%）。"
            "只用于发现异常，不是评分标准。", ""]
    return "\n".join(out)


def render_report(results: list[EvalResult], warns: list[dict], meta: dict,
                  ablation: dict | None = None) -> str:
    v = build_view(results, warns, meta, ablation)
    n = 6 if ablation else 5
    lines = [
        "# 流量异常检测实验报告", "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "",
        _verdict_block(v),
        "## 1. 数据与配置", "", _meta_table(v), "", _classes_line(v), _features_line(v),
        "## 2. 数据泄漏检查", "", _warn_table(v.warnings),
        "## 3. 模型对比", "", _model_table(v), "",
        "## 4. 混淆矩阵", "",
        "| 模型 | TN | FP | FN | TP |", "|---|---|---|---|---|",
    ]
    lines += [f"| {m.model} | {m.tn} | {m.fp} | {m.fn} | {m.tp} |" for m in v.models]
    if v.small_test:
        lines += ["", "> ⚠ 测试集不足 50 条，指标波动很大，不能当作结论。"]
    lines += ["", _ablation_block(v).rstrip(), ""]
    lines += [f"## {n}. 复现方式", "", "```bash",
              f"uv run flowlab demo --split {v.split} --seed {v.seed} "
              f"--models {','.join(m.model for m in v.models)}", "```", "",
              "> 同一个数据指纹 + 同样的切分与随机种子，结果应当逐位一致（浮点误差除外）。",
              "", f"## {n + 1}. 模型参数", ""]
    lines += [f"- `{m.model}`：`{m.params}`" for m in v.models]
    return "\n".join(lines) + "\n"
