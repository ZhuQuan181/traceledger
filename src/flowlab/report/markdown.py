"""报告渲染：一份能贴进论文附录、也能给同事看的 Markdown。"""
from __future__ import annotations

from datetime import datetime

from flowlab.eval.runner import EvalResult
from flowlab.eval.table import markdown_table


def _warn_block(warns: list[dict]) -> str:
    if not warns:
        return "未检测到明显的数据泄漏。\n"
    out = ["| 严重度 | 规则 | 涉及列 | 说明 | 建议 |", "|---|---|---|---|---|"]
    for w in warns:
        out.append(
            f"| {w['severity']} | `{w['rule']}` | {', '.join(map(str, w['columns']))} | "
            f"{w['message']} | {w['suggestion']} |"
        )
    return "\n".join(out) + "\n"


def _meta_block(meta: dict, r0: EvalResult | None) -> str:
    lab = meta.get("labels") or {}
    eng = meta.get("engineering") or {}
    rows = ["| 项 | 值 |", "|---|---|"]
    rows.append(f"| 数据来源 | {meta.get('source', '合成数据')} |")
    rows.append(f"| 样本量 | {meta.get('rows', 0)}（训练 {r0.n_train if r0 else 0} / 测试 {r0.n_test if r0 else 0}） |")
    rows.append(f"| 攻击样本 | 训练 {r0.attack_train if r0 else 0} / 测试 {r0.metrics.get('attack_support', 0) if r0 else 0} |")
    rows.append(f"| 数据指纹 | `{r0.dataset_hash if r0 else ''}` |")
    rows.append(f"| 切分方式 | {r0.split if r0 else ''} |")
    rows.append(f"| 随机种子 | {r0.seed if r0 else 42} |")
    rows.append(f"| 判定阈值 | {r0.threshold if r0 else 0.5} |")
    if lab:
        rows.append(f"| 标签对齐 | {lab.get('mode', 'n/a')}（{lab.get('labelled', 0)}/{lab.get('total', 0)}） |")
    if lab.get("file"):
        rows.append(f"| 标签文件 | `{lab['file']}` |")
    if eng:
        rows.append(f"| 速率兜底 | 最小时长 {eng.get('min_duration_ms')} ms |")
        rows.append(f"| 派生特征 | {'、'.join(eng.get('derived', []))} |")
    return "\n".join(rows) + "\n"


def _ablation_block(ablation: dict | None) -> str:
    if not ablation:
        return ""
    rows = ["| 模型 | AUC（含该列） | AUC（去掉后） | Δ |", "|---|---|---|---|"]
    for r in ablation.get("rows", []):
        aw = "—" if r.get("auc_with") is None else f"{r['auc_with']:.4f}"
        ao = "—" if r.get("auc_without") is None else f"{r['auc_without']:.4f}"
        d = "—" if r.get("delta") is None else f"{r['delta']:+.4f}"
        rows.append(f"| {r['model']} | {aw} | {ao} | {d} |")
    return (f"## 5. 消融：去掉 `{ablation.get('column')}`\n\n" + "\n".join(rows)
            + f"\n\n> {ablation.get('note', '')}\n\n")


def render_report(results: list[EvalResult], warns: list[dict], meta: dict,
                  ablation: dict | None = None) -> str:
    r0 = results[0] if results else None
    lines = [
        "# 流量异常检测实验报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 1. 数据与配置",
        "",
        _meta_block(meta, r0),
        "## 2. 数据泄漏检查",
        "",
        _warn_block(warns),
        "## 3. 模型对比",
        "",
        markdown_table(results),
        "",
        "## 4. 混淆矩阵",
        "",
        "| 模型 | TN | FP | FN | TP |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        c = r.confusion
        lines.append(f"| {r.model} | {c['tn']} | {c['fp']} | {c['fn']} | {c['tp']} |")

    if r0 and r0.n_test < 50:
        lines += ["", "> ⚠ 测试集不足 50 条，指标波动很大，不能当作结论。"]

    lines += ["", _ablation_block(ablation).rstrip() or "", ""]

    section = 6 if ablation else 5
    lines += [f"## {section}. 复现方式", "", "```bash",
              f"uv run flowlab demo --split {r0.split if r0 else 'temporal'} "
              f"--seed {r0.seed if r0 else 42} --models {','.join(r.model for r in results)}",
              "```", "",
              "> 同一个数据指纹 + 同样的切分与随机种子，结果应当逐位一致（浮点误差除外）。",
              "", f"## {section + 1}. 模型参数", ""]
    for r in results:
        lines.append(f"- `{r.model}`（{r.kind}）：`{r.params}`")
    return "\n".join(lines) + "\n"
