"""终端对比表。"""

from __future__ import annotations

import json

from flowlab.eval.runner import EvalResult


def markdown_table(results: list[EvalResult]) -> str:
    head = "| 模型 | AUC | PR-AUC | F1 | 精确率 | 召回率 | 误报率 | 耗时(s) |"
    sep = "|---|---|---|---|---|---|---|---|"
    rows = []
    for r in results:
        m = r.metrics
        auc = "—" if m.get("auc") is None else f"{m['auc']:.4f}"
        pr_auc = "—" if m.get("pr_auc") is None else f"{m['pr_auc']:.4f}"
        rows.append(
            f"| {r.model} | {auc} | {pr_auc} | {m['f1']:.4f} | {m['precision']:.4f} | "
            f"{m['recall']:.4f} | {m.get('fpr') if m.get('fpr') is not None else '—'} | {r.duration_s:.2f} |"
        )
    return "\n".join([head, sep, *rows])


def as_json(results: list[EvalResult]) -> str:
    return json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2)
