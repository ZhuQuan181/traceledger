"""统一的输出载荷：CLI、API、历史库共用同一份结构。"""
from __future__ import annotations

import pandas as pd

from flowlab.eval.runner import EvalResult
from flowlab.eval.verdict import judge
from flowlab.report.html import render_html
from flowlab.report.markdown import render_report


def class_distribution(df: pd.DataFrame, label_col: str = "label", top: int = 8) -> list[dict]:
    """标签分布（按数量降序，超出 top 的合并为「其他」）。"""
    if label_col not in df.columns:
        return []
    counts = df[label_col].astype(str).str.strip().value_counts(dropna=False)
    rows = [{"label": str(k), "count": int(v)} for k, v in counts.head(top).items()]
    rest = int(counts.iloc[top:].sum()) if len(counts) > top else 0
    if rest:
        rows.append({"label": "其他", "count": rest})
    return rows


def build_payload(df: pd.DataFrame, results: list[EvalResult], warns: list[dict],
                  source: str, meta: dict | None = None,
                  ablation: dict | None = None,
                  label_col: str = "label") -> dict:
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
        "format": meta.get("format", {}),
        "classes": class_distribution(df, label_col),
        "features": {
            "used": results[0].features if results else [],
            "encoded": results[0].encoded_features if results else 0,
        },
    }
    report_meta = {"source": source, "rows": len(df), "labels": dataset["labels"],
                   "engineering": dataset["engineering"], "format": dataset["format"],
                   "classes": dataset["classes"], "features": dataset["features"],
                   "attack_support": dataset["attack_test"]}

    verdict = judge(best.metrics if best else {}, warns, dataset["test"], ablation,
                    used_features=dataset["features"]["used"])
    report_meta["verdict"] = {"level": verdict.level, "headline": verdict.headline,
                              "reasons": verdict.reasons, "checks": verdict.checks}

    return {
        "dataset": dataset,
        "verdict": report_meta["verdict"],
        "warnings": warns,
        "results": [r.to_dict() for r in results],
        "best_model": best.model if best else None,
        "top_flows": best.top_flows if best else [],
        "score_curve": best.score_curve if best else [],
        "ablation": ablation,
        "report_md": render_report(results, warns, report_meta, ablation=ablation),
        "report_html": render_html(results, warns, report_meta, ablation=ablation),
    }
