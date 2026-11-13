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


def _data_block(meta: dict) -> str:
    lab = meta.get("labels") or {}
    eng = meta.get("engineering") or {}
    rows = ["| 项 | 值 |", "|---|---|"]
    if lab:
        rows.append(f"| 标签对齐 | {lab.get('mode', 'n/a')}（{lab.get('labelled', 0)}/{meta.get('rows', 0)} 条有标签） |")
    if lab.get("file"):
        rows.append(f"| 标签文件 | `{lab['file']}` |")
    if r0_attack := meta.get("attack_support"):
        rows.append(f"| 测试集攻击样本 | {r0_attack} 条 |")
    if eng:
        rows.append(f"| 速率兜底 | 最小时长 {eng.get('min_duration_ms')} ms；派生 {'、'.join(eng.get('derived', []))} |")
        rows.append(f"| 说明 | {eng.get('note', '')} |")
    return "\n".join(rows) + "\n"


def render_report(results: list[EvalResult], warns: list[dict], meta: dict) -> str:
    r0 = results[0] if results else None
    lines = [
        "# 流量异常检测实验报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 数据来源：{meta.get('source', '合成数据')}",
        f"- 样本量：{meta.get('rows', r0.n_train + r0.n_test if r0 else 0)}"
        f"（训练 {r0.n_train if r0 else 0} / 测试 {r0.n_test if r0 else 0}）",
        f"- 数据指纹：`{r0.dataset_hash if r0 else 'n/a'}`",
        f"- 切分方式：{r0.split if r0 else 'n/a'}（time-ordered）" if r0 and r0.split == "temporal"
        else f"- 切分方式：{r0.split if r0 else 'n/a'}",
        f"- 判定阈值：{r0.threshold if r0 else 0.5}",
        "",
        "## 1. 数据来源与特征",
        "",
        _data_block(meta),
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

    lines += ["", "## 5. 复现方式", "", "```bash", "uv run flowlab demo --split "
              f"{r0.split if r0 else 'temporal'} --models {','.join(r.model for r in results)}", "```", "",
              "> 同一个数据指纹 + 同样的切分与随机种子，结果应当逐位一致（浮点误差除外）。", "",
              "## 6. 模型参数", ""]
    for r in results:
        lines.append(f"- `{r.model}`（{r.kind}）：`{r.params}`")
    return "\n".join(lines) + "\n"
