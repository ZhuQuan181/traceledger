"""统一的输出载荷：CLI、API、历史库共用同一份结构。"""
from __future__ import annotations

import pandas as pd

from flowlab.eval.runner import EvalResult
from flowlab.report.html import render_html
from flowlab.report.markdown import render_report


def build_payload(df: pd.DataFrame, results: list[EvalResult], warns: list[dict],
                  source: str, meta: dict | None = None,
                  ablation: dict | None = None) -> dict:
    meta = dict(meta or {})
    r0 = results[0] if results else None
    best = max(results, key=lambda r: (r.metrics.get("auc") or 0)) if results else None

    dataset = {
        "source": source,
        "rows": int(len(df)),
        "train": r0.n_train if r0 else 0,
        "test": r0.n_test if r0 else 0,
        "hash": r0.dataset_hash if r0 else "",
        "split": r0.split if r0 else "",
        "threshold": r0.threshold if r0 else 0.5,
        "seed": r0.seed if r0 else 42,
        "attack_train": r0.attack_train if r0 else 0,
        "attack_test": r0.metrics.get("attack_support", 0) if r0 else 0,
        "labels": meta.get("labels", {}),
        "engineering": meta.get("engineering", {}),
    }
    report_meta = {"source": source, "rows": len(df), "labels": dataset["labels"],
                   "engineering": dataset["engineering"],
                   "attack_support": dataset["attack_test"]}
    return {
        "dataset": dataset,
        "warnings": warns,
        "results": [r.to_dict() for r in results],
        "best_model": best.model if best else None,
        "top_flows": best.top_flows if best else [],
        "score_curve": best.score_curve if best else [],
        "ablation": ablation,
        "report_md": render_report(results, warns, report_meta, ablation=ablation),
        "report_html": render_html(results, warns, report_meta, ablation=ablation),
    }
