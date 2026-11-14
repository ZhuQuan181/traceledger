"""Markdown 报告：只做排版，所有数值来自 ReportView。"""

from __future__ import annotations

from flowlab.eval.runner import EvalResult
from flowlab.report.view import ReportView, build_view


def _cell(value) -> str:
    """Markdown 表格单元格只做必要转义，避免标签/主机名破坏列结构。"""
    return (
        str(value if value is not None else "—")
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", "<br>")
    )


def _meta_table(v: ReportView) -> str:
    split = v.split
    if v.split_fallback:
        split = "随机切分（请求时间切分，因时间戳不足已退化）"
    elif split == "temporal":
        split = "时间切分"
    elif split == "random":
        split = "分层随机切分"
    environment = " · ".join(
        f"{key} {value}" for key, value in v.environment.items() if value is not None
    )
    rows = [
        ("数据来源", f"{v.source}（{v.fmt}）"),
        ("样本量", f"{v.rows}（训练 {v.train} / 验证 {v.validation} / 测试 {v.test}）"),
        (
            "攻击样本",
            f"训练 {v.attack_train} / 验证 {v.attack_validation} / 测试 {v.attack_test}",
        ),
        ("数据指纹", f"`{v.hash}`"),
        ("实验指纹", f"`{v.experiment_fingerprint}`"),
        ("运行环境", environment or "—"),
        ("切分方式", split),
        ("泛化场景", v.generalization),
        ("随机种子", str(v.seed)),
        (
            "判定阈值",
            f"{v.threshold}（{_threshold_source(v)}）",
        ),
        ("模型选择", "验证集 AUC（测试集只做最终报告）"),
        (
            "标签对齐",
            f"{v.labels_mode}（{v.labels_labelled}/{v.labels_total}）"
            if v.labels_total
            else v.labels_mode,
        ),
        ("速率兜底", f"{v.min_duration_ms} ms"),
    ]
    return "| 项 | 值 |\n|---|---|\n" + "\n".join(
        f"| {_cell(k)} | {_cell(val)} |" for k, val in rows
    )


def _threshold_source(v: ReportView) -> str:
    if v.threshold_source == "validation_f1":
        return "验证集 F1 自动选择"
    if v.threshold_source == "validation_fpr":
        target = (
            f"≤{v.threshold_target_fpr:.2%}" if v.threshold_target_fpr is not None else "目标值"
        )
        return f"验证集目标误报率自动选择（{target}）"
    return "人工指定"


def _classes_line(v: ReportView) -> str:
    if not v.classes:
        return ""
    parts = [f"{c['label']} {c['count']:,}" for c in v.classes]
    return "\n**类别分布**：" + " · ".join(parts) + "\n"


def _features_line(v: ReportView) -> str:
    if not v.features:
        return ""
    shown = ", ".join(f"`{f}`" for f in v.features)
    return (
        f"\n**参与训练的特征**：{len(v.features)} 列（编码后 {v.encoded_features} 维）\n\n{shown}\n"
    )


def _quality_block(v: ReportView) -> str:
    quality = v.quality
    if not quality:
        return ""
    rare = quality.get("rare_classes") or []
    examples = quality.get("conflict_examples") or []
    rows = [
        ("缺失标签", f"{int(quality.get('missing_labels') or 0):,} 条"),
        (
            "完全重复行",
            f"{int(quality.get('duplicate_rows') or 0):,} 行"
            f"（{float(quality.get('duplicate_rate') or 0):.2%}）",
        ),
        (
            "同一实体多标签",
            f"{int(quality.get('conflict_groups') or 0):,} 组"
            f" / {int(quality.get('conflict_rows') or 0):,} 行"
            if quality.get("conflict_key")
            else "无可用实体键",
        ),
        (
            "稀有类别",
            " · ".join(f"{row['label']} {row['count']}" for row in rare)
            if rare
            else f"无（阈值 <{quality.get('rare_threshold', 20)}）",
        ),
    ]
    out = [
        "### 标签质量",
        "",
        "| 检查 | 结果 |",
        "|---|---|",
        *[f"| {_cell(name)} | {_cell(value)} |" for name, value in rows],
    ]
    if examples:
        out += ["", "冲突示例："]
        out += [
            f"- `{_cell(row['entity'])}`：{'、'.join(_cell(v) for v in row['labels'])}"
            for row in examples
        ]
    if rare:
        out += ["", "> 稀有类别可能无法支撑稳定结论，建议合并、补样或单独报告。"]
    out.append("")
    return "\n".join(out)


def _warn_table(warns: list[dict]) -> str:
    if not warns:
        return "未检测到明显的数据泄漏。\n"
    out = ["| 严重度 | 规则 | 涉及列 | 说明 | 建议 |", "|---|---|---|---|---|"]
    for w in warns:
        out.append(
            f"| {_cell(w['severity'])} | `{_cell(w['rule'])}` | "
            f"{_cell(', '.join(map(str, w['columns'])))} | "
            f"{_cell(w['message'])} | {_cell(w['suggestion'])} |"
        )
    return "\n".join(out) + "\n"


def _model_table(v: ReportView) -> str:
    head = "| 模型 | 类型 | 验证 AUC | 测试 AUC | 测试 PR-AUC | 测试 F1 | 精确率 | 召回率 | 误报率 | 阈值 | 耗时 | TP | FP | FN | TN |"
    sep = "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    rows = [
        f"| {_cell(m.model)}{' 🏆' if m.is_best else ''} | {_cell(m.kind_cn)} | {m.validation_auc} | {m.auc} | {m.pr_auc} | {m.f1} | {m.precision} | "
        f"{m.recall} | {m.fpr} | {m.threshold} | {m.duration} | {m.tp} | {m.fp} | {m.fn} | {m.tn} |"
        for m in v.models
    ]
    return "\n".join([head, sep, *rows])


def _threshold_table(v: ReportView) -> str:
    if not v.threshold_scan:
        return ""
    rows = ["| 阈值 | 精确率 | 召回率 | F1 | 误报率 |", "|---|---|---|---|---|"]
    for row in v.threshold_scan:
        fpr = "—" if row.get("fpr") is None else f"{row['fpr']:.2%}"
        rows.append(
            f"| {row['threshold']:.2f} | {row['precision']:.4f} | "
            f"{row['recall']:.4f} | {row['f1']:.4f} | {fpr} |"
        )
    return (
        "### 阈值权衡（测试集诊断）\n\n"
        + "\n".join(rows)
        + "\n\n> 该扫描只用于展示部署权衡，不能拿测试集挑阈值；"
        "自动阈值只使用验证集。\n"
    )


def _sample_rows(rows: list[dict], limit: int = 8) -> list[dict]:
    """曲线和分箱表只保留可读的抽样点，完整数据仍留在 JSON 报告里。"""
    if len(rows) <= limit:
        return rows
    indices = sorted({round(index * (len(rows) - 1) / (limit - 1)) for index in range(limit)})
    return [rows[index] for index in indices]


def _curves_block(v: ReportView) -> str:
    if not (v.roc_curve or v.pr_curve or v.calibration):
        return ""
    out = [f"### 排序与校准（{v.best_model}）", ""]
    if v.brier_score is not None:
        out += [f"**Brier score**：`{v.brier_score:.4f}`（越低越好，仅监督模型）", ""]
    if v.calibration_note:
        out += [f"> {v.calibration_note}", ""]
    if v.roc_curve:
        out += ["| ROC · FPR | TPR | 阈值 |", "|---|---|---|"]
        for row in _sample_rows(v.roc_curve):
            threshold = "—" if row.get("threshold") is None else f"{row['threshold']:.4f}"
            out.append(f"| {row['fpr']:.4f} | {row['tpr']:.4f} | {threshold} |")
        out.append("")
    if v.pr_curve:
        out += ["| PR · 召回率 | 精确率 | 阈值 |", "|---|---|---|"]
        for row in _sample_rows(v.pr_curve):
            threshold = "—" if row.get("threshold") is None else f"{row['threshold']:.4f}"
            out.append(f"| {row['recall']:.4f} | {row['precision']:.4f} | {threshold} |")
        out.append("")
    if v.calibration:
        out += ["| 校准 · 平均预测概率 | 实际攻击比例 |", "|---|---|"]
        out += [
            f"| {row['mean_predicted']:.4f} | {row['fraction_positive']:.4f} |"
            for row in _sample_rows(v.calibration)
        ]
        out.append("")
    return "\n".join(out)


def _ablation_block(v: ReportView, section: int) -> str:
    if not v.ablation:
        return ""
    rows = ["| 模型 | AUC（含该列） | AUC（去掉后） | Δ |", "|---|---|---|---|"]
    for r in v.ablation.get("rows", []):
        aw = "—" if r.get("auc_with") is None else f"{r['auc_with']:.4f}"
        ao = "—" if r.get("auc_without") is None else f"{r['auc_without']:.4f}"
        d = "—" if r.get("delta") is None else f"{r['delta']:+.4f}"
        rows.append(f"| {r['model']} | {aw} | {ao} | {d} |")
    return (
        f"## {section:02d}. 消融：去掉 `"
        + str(v.ablation.get("column"))
        + "`\n\n"
        + "\n".join(rows)
        + f"\n\n> {v.ablation.get('note', '')}\n\n"
    )


def _flows_block(v: ReportView) -> str:
    if not v.flows:
        return ""
    rows = [
        f"| {_cell(f.get('src_ip', '—'))} | {_cell(f.get('dst_ip', '—'))} | "
        f"{_cell(f.get('dst_port', '—'))} | {_cell(f.get('protocol', '—'))} | "
        f"{_cell(f.get('score', '—'))} | {_cell(f.get('label', '—'))} |"
        for f in v.flows
    ]
    return (
        "| 源 | 目的 | 端口 | 协议 | 分数 | 真实标签 |\n"
        "|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n"
    )


def _error_rows(rows: list[dict]) -> list[str]:
    return [
        f"| {_cell(r.get('src_ip', '—'))} | {_cell(r.get('dst_ip', '—'))} | "
        f"{_cell(r.get('dst_port', '—'))} | {_cell(r.get('score', '—'))} | "
        f"{_cell(r.get('label', '—'))} |"
        for r in rows
    ]


def _investigation_block(v: ReportView) -> str:
    if not (v.by_label or v.source_ranking or v.false_positives or v.false_negatives):
        return ""
    out: list[str] = []
    if v.by_label:
        out += [
            "### 按真实类型拆分",
            "",
            "| 类型 | 性质 | 样本 | 判为攻击 | 比例 |",
            "|---|---|---|---|---|",
        ]
        for row in v.by_label:
            measure = "误报率" if row.get("kind") == "benign" else "召回率"
            rate = "—" if row.get("rate") is None else f"{row['rate']:.2%}"
            out.append(
                f"| {_cell(row.get('label'))} | {measure} | {int(row.get('total', 0)):,} | "
                f"{int(row.get('flagged', 0)):,} | {rate} |"
            )
        out.append("")
    if v.source_ranking:
        out += [
            "### 先排查的源 IP",
            "",
            "| 源 IP | 告警 | 真攻击 | 误报 | 最高分 |",
            "|---|---|---|---|---|",
        ]
        for row in v.source_ranking:
            out.append(
                f"| {_cell(row.get('src_ip'))} | {int(row.get('alerts', 0)):,} | "
                f"{int(row.get('true_attacks', 0)):,} | {int(row.get('false_alarms', 0)):,} | "
                f"{row.get('max_score', '—')} |"
            )
        out.append("")
    for title, rows in (
        ("典型漏报（攻击但未过阈值）", v.false_negatives),
        ("典型误报（正常但被判为攻击）", v.false_positives),
    ):
        if not rows:
            continue
        out += [
            f"### {title}",
            "",
            "| 源 | 目的 | 端口 | 分数 | 标签 |",
            "|---|---|---|---|---|",
            *_error_rows(rows),
            "",
        ]
    return "\n".join(out)


def _verdict_block(v: ReportView) -> str:
    """结论区块：放最前面，回答"这组数字能不能用"。"""
    vd = v.verdict or {}
    if not vd:
        return ""
    icon = {"ok": "✅", "warn": "⚠️", "fail": "⛔"}.get(vd.get("level", ""), "•")
    out = ["## 0. 结论", "", f"### {icon} {vd.get('headline', '')}", ""]
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
    out += [
        "> 判断依据：CICIDS 类数据集上的常见区间（AUC 0.93–0.99、误报率 0.5%–8%）。"
        "只用于发现异常，不是评分标准。",
        "",
    ]
    return "\n".join(out)


def _checklist_block(v: ReportView) -> str:
    """投稿前自查：人工逐条打勾，和自动判断互补。"""
    if not v.checklist:
        return ""
    passed = sum(1 for i in v.checklist if i["ok"])
    out = [f"## 自查清单（{passed}/{len(v.checklist)}）", ""]
    for i in v.checklist:
        mark = "x" if i["ok"] else " "
        out.append(f"- [{mark}] **{i['item']}** — {i['detail']}")
    if passed < len(v.checklist):
        out += ["", "> 未勾选的项补完再投稿；这些是审稿人最容易问到的。"]
    out.append("")
    return "\n".join(out)


def render_report(
    results: list[EvalResult], warns: list[dict], meta: dict, ablation: dict | None = None
) -> str:
    v = build_view(results, warns, meta, ablation)
    next_section = 5
    lines = [
        "# 流量异常检测实验报告",
        "",
        f"- 生成时间：{v.generated_at or '—'}",
        f"- 实验指纹：`{v.experiment_fingerprint}`",
        "",
        _verdict_block(v),
        _checklist_block(v),
        "## 1. 数据与配置",
        "",
        _meta_table(v),
        "",
        _classes_line(v),
        _quality_block(v),
        _features_line(v),
        "## 2. 数据泄漏检查",
        "",
        _warn_table(v.warnings),
        "## 3. 模型对比",
        "",
        "> 最佳模型只按验证集 AUC 选择；下表主指标均来自未参与选择与调参的测试集。",
        "",
        _model_table(v),
        "",
        _threshold_table(v),
        _curves_block(v),
        "",
        "## 4. 混淆矩阵",
        "",
        "> 混淆矩阵对应测试集与报告中的判定阈值。",
        "",
        "| 模型 | TN | FP | FN | TP |",
        "|---|---|---|---|---|",
    ]
    lines += [f"| {m.model} | {m.tn} | {m.fp} | {m.fn} | {m.tp} |" for m in v.models]
    if v.small_test:
        lines += ["", "> ⚠ 测试集不足 50 条，指标波动很大，不能当作结论。"]
    if v.ablation:
        lines += ["", _ablation_block(v, next_section).rstrip(), ""]
        next_section += 1
    lines += [f"## {next_section}. 最可疑的流", "", _flows_block(v), ""]
    next_section += 1
    investigation = _investigation_block(v)
    if investigation:
        lines += [f"## {next_section}. 调查线索", "", investigation, ""]
        next_section += 1
    command = v.reproduction_command or (
        f"uv run flowlab demo --split {v.split_requested} --seed {v.seed} "
        f"--threshold {v.threshold} --threshold-mode {v.threshold_mode} "
        + (
            f"--target-fpr {v.threshold_target_fpr} "
            if v.threshold_mode == "fpr" and v.threshold_target_fpr is not None
            else ""
        )
        + f"--models {','.join(m.model for m in v.models)}"
    )
    source_note = (
        "上传文件的原路径不会写入历史；复现前请重新选择同名数据与标签文件。"
        if v.source_kind == "upload"
        else ""
    )
    lines += [
        f"## {next_section}. 复现方式",
        "",
        "```bash",
        command,
        "```",
        "",
        f"> 数据指纹 `{v.hash}` + 切分 + 随机种子决定指标；实验指纹 `{v.experiment_fingerprint}` "
        "用于核对两次实验的计算结果是否一致。报告含生成时间，文件字节不保证完全相同。"
        + (f" {source_note}" if source_note else ""),
        "",
        f"## {next_section + 1}. 模型参数",
        "",
    ]
    lines += [f"- `{m.model}`：`{m.params}`" for m in v.models]
    return "\n".join(lines) + "\n"
