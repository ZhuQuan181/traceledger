"""跨实验对比：CLI、API 与 Web 共用同一份可比性和指标结构。"""

from __future__ import annotations

import json
from typing import Any

MIN_RUNS = 2
MAX_RUNS = 4


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and value == value:
        return float(value)
    return None


def _best_result(payload: dict) -> dict:
    model = payload.get("best_model")
    results = payload.get("results") or []
    if model:
        for result in results:
            if result.get("model") == model:
                return result
    return results[0] if results else {}


def _summary(record: dict) -> dict:
    payload = record.get("payload") or {}
    dataset = payload.get("dataset") or {}
    experiment = payload.get("experiment") or {}
    best = _best_result(payload)
    validation = best.get("validation_metrics") or {}
    metrics = best.get("metrics") or {}
    features = list((dataset.get("features") or {}).get("used") or [])
    return {
        "id": str(record.get("id") or payload.get("run_id") or "—"),
        "created_at": record.get("created_at") or payload.get("generated_at") or "",
        "source": record.get("source") or dataset.get("source") or "",
        "dataset_hash": record.get("dataset_hash") or dataset.get("hash") or "",
        "split": record.get("split") or dataset.get("split") or experiment.get("split") or "",
        "seed": dataset.get("seed", experiment.get("seed")),
        "rows": dataset.get("rows") or record.get("rows"),
        "train": dataset.get("train"),
        "validation": dataset.get("validation"),
        "validation_size": experiment.get("validation_size"),
        "test": dataset.get("test") or record.get("test"),
        "attack_test": dataset.get("attack_test") or metrics.get("attack_support"),
        "model": best.get("model") or payload.get("best_model"),
        "validation_auc": _number(validation.get("auc")),
        "test_auc": _number(metrics.get("auc")),
        "pr_auc": _number(metrics.get("pr_auc")),
        "f1": _number(metrics.get("f1")),
        "precision": _number(metrics.get("precision")),
        "recall": _number(metrics.get("recall")),
        "fpr": _number(metrics.get("fpr")),
        "threshold": (
            _number(best.get("threshold"))
            if best.get("threshold") is not None
            else _number(dataset.get("threshold"))
        ),
        "threshold_source": best.get("threshold_source") or dataset.get("threshold_source"),
        "threshold_mode": experiment.get("threshold_mode") or dataset.get("threshold_mode"),
        "duration_s": _number(best.get("duration_s")),
        "features": features,
        "encoded_features": (dataset.get("features") or {}).get("encoded"),
        "experiment_fingerprint": payload.get("experiment_fingerprint")
        or dataset.get("experiment_fingerprint"),
    }


def _delta(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline is None:
        return None
    return round(value - baseline, 4)


def _check(key: str, label: str, ok: bool, detail: str) -> dict:
    return {"key": key, "label": label, "ok": ok, "detail": detail}


def _md_cell(value: Any) -> str:
    if value is None:
        return "—"
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", "<br>")
    )


def _fmt(value: Any, digits: int = 4, pct: bool = False) -> str:
    if value is None:
        return "—"
    if pct:
        return f"{value:.2%}"
    return f"{value:.{digits}f}"


def _fmt_delta(value: float | None, pct: bool = False) -> str:
    if value is None:
        return "—"
    if pct:
        return f"{value:+.2%}"
    return f"{value:+.4f}"


def _markdown(summary: dict, runs: list[dict]) -> str:
    lines = [
        "# FlowLab 跨实验对比",
        "",
        f"> {summary['headline']}",
        "",
    ]
    if summary["warnings"]:
        lines.extend(f"> ⚠ {message}" for message in summary["warnings"])
        lines.append("")
    lines.extend(
        [
            "| 实验 | 时间 | 模型 | 验证 AUC | 测试 AUC | PR-AUC | F1 | 召回率 | 误报率 | 阈值 | 切分 | 测试样本 |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for run in runs:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(run["id"]),
                    _md_cell((run["created_at"] or "")[:19]),
                    _md_cell(run["model"]),
                    _fmt(run["validation_auc"]),
                    _fmt(run["test_auc"]),
                    _fmt(run["pr_auc"]),
                    _fmt(run["f1"]),
                    _fmt(run["recall"]),
                    _fmt(run["fpr"], pct=True),
                    _fmt(run["threshold"], digits=2),
                    _md_cell(run["split"]),
                    _md_cell(run["test"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            f"变化相对首个实验 `{_md_cell(runs[0]['id'])}`；误报率越低越好。",
            "",
            "| 实验 | Δ验证 AUC | Δ测试 AUC | ΔPR-AUC | ΔF1 | Δ召回率 | Δ误报率 |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for run in runs:
        delta = run["delta"]
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(run["id"]),
                    _fmt_delta(delta["validation_auc"]),
                    _fmt_delta(delta["test_auc"]),
                    _fmt_delta(delta["pr_auc"]),
                    _fmt_delta(delta["f1"]),
                    _fmt_delta(delta["recall"]),
                    _fmt_delta(delta["fpr"], pct=True),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def build_comparison(records: list[dict]) -> dict:
    """构造对比结果；不直接比较不可比实验，但仍保留数字供排查。"""
    if not MIN_RUNS <= len(records) <= MAX_RUNS:
        raise ValueError(f"一次只能对比 {MIN_RUNS}–{MAX_RUNS} 次实验")

    runs = [_summary(record) for record in records]
    hashes = {run["dataset_hash"] for run in runs if run["dataset_hash"]}
    same_dataset = len(hashes) == 1 and all(run["dataset_hash"] for run in runs)
    feature_sets = [(tuple(run["features"]), run["encoded_features"]) for run in runs]
    same_features = bool(feature_sets[0][0]) and all(
        features == feature_sets[0] for features in feature_sets[1:]
    )
    split_signatures = [
        (
            run["split"],
            run["seed"] if run["split"] in {"random", "group"} else None,
            run["validation"],
            run["test"],
        )
        for run in runs
    ]
    same_split = all(signature == split_signatures[0] for signature in split_signatures[1:])

    hash_text = next(iter(hashes)) if same_dataset else "、".join(sorted(hashes)) or "缺失"
    checks = [
        _check(
            "dataset",
            "数据指纹",
            same_dataset,
            f"全部使用 {hash_text}" if same_dataset else f"数据指纹不一致：{hash_text}",
        ),
        _check(
            "features",
            "特征矩阵",
            same_features,
            f"特征列一致（{len(feature_sets[0][0])} 列）"
            if same_features
            else "特征列或编码维度不一致",
        ),
        _check(
            "split",
            "切分与验证/测试集",
            same_split,
            "切分方式、随机种子、验证集与测试集大小一致"
            if same_split
            else "切分方式、随机种子、验证集或测试集大小不一致",
        ),
    ]

    if not same_dataset:
        status = "incompatible"
        headline = "不可直接比较：数据来源不同，指标差异不能归因于模型或阈值"
    elif not same_features or not same_split:
        status = "limited"
        headline = "只能作为对照：数据相同，但特征矩阵或切分不同，指标差异不能直接归因"
    else:
        status = "comparable"
        headline = "可直接比较：同数据、同特征、同切分"

    warnings = [check["detail"] for check in checks if not check["ok"]]
    baseline = runs[0]
    for run in runs:
        run["delta"] = {
            key: _delta(run[key], baseline[key])
            for key in ("validation_auc", "test_auc", "pr_auc", "f1", "recall", "fpr")
        }

    summary = {
        "status": status,
        "comparable": status == "comparable",
        "headline": headline,
        "warnings": warnings,
        "checks": checks,
        "baseline_run_id": baseline["id"],
        "command": "uv run flowlab compare " + " ".join(run["id"] for run in runs),
    }
    summary["runs"] = runs
    summary["markdown"] = _markdown(summary, runs)
    return summary


def load_comparison(run_ids: list[str]) -> dict:
    unique = list(dict.fromkeys(run_ids))
    if len(unique) != len(run_ids):
        raise ValueError("同一次对比不能重复选择同一个实验")
    if not MIN_RUNS <= len(unique) <= MAX_RUNS:
        raise ValueError(f"一次只能对比 {MIN_RUNS}–{MAX_RUNS} 次实验")

    from flowlab.store import get_run

    records = []
    missing = []
    for run_id in unique:
        record = get_run(run_id)
        if record is None:
            missing.append(run_id)
        else:
            records.append(record)
    if missing:
        raise LookupError("找不到这些实验：" + "、".join(missing))
    return build_comparison(records)


def comparison_json(comparison: dict) -> str:
    return json.dumps(comparison, ensure_ascii=False, indent=2)
