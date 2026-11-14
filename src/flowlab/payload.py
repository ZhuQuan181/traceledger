"""统一的输出载荷：CLI、API、历史库共用同一份结构。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

import pandas as pd

from flowlab.eval.checklist import build_checklist
from flowlab.eval.runner import EvalResult, select_best, selection_auc
from flowlab.eval.verdict import judge
from flowlab.report.html import render_html
from flowlab.report.markdown import render_report


def _experiment_fingerprint(
    dataset: dict, results: list[dict], warns: list[dict], ablation: dict | None
) -> str:
    """指标与决策内容的稳定指纹；刻意排除耗时和生成时间。"""
    stable_results = []
    for row in results:
        item = dict(row)
        item.pop("duration_s", None)
        stable_results.append(item)
    core = {
        "dataset": {
            key: dataset.get(key)
            for key in (
                "hash",
                "rows",
                "train",
                "validation",
                "test",
                "split",
                "seed",
                "threshold",
                "threshold_mode",
                "threshold_source",
                "selection",
            )
        },
        "results": stable_results,
        "warnings": warns,
        "ablation": ablation,
    }
    blob = json.dumps(core, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _class_distribution(df: pd.DataFrame, label_col: str = "label", top: int = 8) -> list[dict]:
    """标签分布（按数量降序，超出 top 的合并为「其他」）。"""
    if label_col not in df.columns:
        return []
    counts = df[label_col].astype(str).str.strip().value_counts(dropna=False)
    rows = [{"label": str(k), "count": int(v)} for k, v in counts.head(top).items()]
    rest = int(counts.iloc[top:].sum()) if len(counts) > top else 0
    if rest:
        rows.append({"label": "其他", "count": rest})
    return rows


def build_payload(
    df: pd.DataFrame,
    results: list[EvalResult],
    warns: list[dict],
    source: str,
    meta: dict | None = None,
    ablation: dict | None = None,
    label_col: str = "label",
) -> dict:
    meta = dict(meta or {})
    r0 = results[0] if results else None
    best = select_best(results)

    dataset = {
        "source": source,
        "rows": int(len(df)),
        "train": r0.n_train if r0 else 0,
        "validation": r0.n_validation if r0 else 0,
        "test": r0.n_test if r0 else 0,
        "hash": r0.dataset_hash if r0 else "",
        "split": r0.split if r0 else "",
        "split_requested": r0.split_requested if r0 else "",
        "split_fallback": bool(r0 and r0.split_requested == "temporal" and r0.split != "temporal"),
        "split_diagnostics": r0.split_diagnostics if r0 else {},
        "generalization": (
            "未来时间外推"
            if r0 and r0.split == "temporal"
            else "未见实体泛化"
            if r0 and r0.split == "group"
            else "同分布随机泛化"
        ),
        "threshold": best.threshold if best else 0.5,
        "threshold_mode": meta.get("threshold_mode")
        or (meta.get("experiment") or {}).get("threshold_mode", "fixed"),
        "threshold_source": best.threshold_source if best else "fixed",
        "seed": r0.seed if r0 else 42,
        "attack_train": r0.attack_train if r0 else 0,
        "attack_validation": r0.attack_validation if r0 else 0,
        "attack_test": r0.metrics.get("attack_support", 0) if r0 else 0,
        "selection": {
            "rule": "validation_auc",
            "validation_auc": selection_auc(best) if best else None,
            "test_auc": best.metrics.get("auc") if best else None,
        },
        "labels": meta.get("labels", {}),
        "engineering": meta.get("engineering", {}),
        "format": meta.get("format", {}),
        "classes": _class_distribution(df, label_col),
        "features": {
            "used": results[0].features if results else [],
            "encoded": results[0].encoded_features if results else 0,
        },
    }
    result_dicts = [r.to_dict() for r in results]
    recommendation_fingerprint = _experiment_fingerprint(dataset, result_dicts, warns, ablation)
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    experiment = meta.get("experiment") or {
        "source": source,
        "split": dataset["split_requested"] or dataset["split"],
        "split_effective": dataset["split"],
        "command": "",
    }
    report_meta = {
        "source": source,
        "rows": len(df),
        "labels": dataset["labels"],
        "engineering": dataset["engineering"],
        "format": dataset["format"],
        "classes": dataset["classes"],
        "features": dataset["features"],
        "attack_support": dataset["attack_test"],
        "investigation": (best.to_dict().get("by_label", []) if best else []),
        "experiment": experiment,
        "generated_at": generated_at,
        "experiment_fingerprint": recommendation_fingerprint,
    }
    dataset["experiment_fingerprint"] = recommendation_fingerprint

    verdict = judge(
        best.metrics if best else {},
        warns,
        dataset["test"],
        ablation,
        used_features=dataset["features"]["used"],
        split_requested=dataset["split_requested"] or dataset["split"],
        split_effective=dataset["split"],
    )
    report_meta["verdict"] = {
        "level": verdict.level,
        "headline": verdict.headline,
        "reasons": verdict.reasons,
        "checks": verdict.checks,
    }
    checklist = build_checklist(dataset, warns, ablation, unresolved_leak=verdict.level == "fail")
    report_meta["checklist"] = checklist

    return {
        "dataset": dataset,
        "experiment": experiment,
        "generated_at": generated_at,
        "experiment_fingerprint": recommendation_fingerprint,
        "verdict": report_meta["verdict"],
        "checklist": checklist,
        "warnings": warns,
        "results": result_dicts,
        "best_model": best.model if best else None,
        "best_model_selection": "validation_auc",
        "top_flows": best.top_flows if best else [],
        "score_curve": best.score_curve if best else [],
        "score_curve_basis": best.score_curve_basis if best else "order",
        "threshold_scan": best.threshold_scan if best else [],
        "investigation": {
            "by_label": best.by_label if best else [],
            "false_positives": best.false_positives if best else [],
            "false_negatives": best.false_negatives if best else [],
            "source_ranking": best.source_ranking if best else [],
        },
        "ablation": ablation,
        "report_md": render_report(results, warns, report_meta, ablation=ablation),
        "report_html": render_html(results, warns, report_meta, ablation=ablation),
    }
