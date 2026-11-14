"""指标计算：ROC-AUC / PR-AUC / F1 / 精确率 / 召回率 / 误报率 / 混淆矩阵。"""

from __future__ import annotations

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


def compute_metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float = 0.5) -> dict:
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    y_pred = (scores >= threshold).astype(int)

    try:
        auc = float(roc_auc_score(y_true, scores)) if len(np.unique(y_true)) > 1 else float("nan")
    except ValueError:
        auc = float("nan")
    try:
        pr_auc = (
            float(average_precision_score(y_true, scores))
            if len(np.unique(y_true)) > 1
            else float("nan")
        )
    except ValueError:
        pr_auc = float("nan")

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    fpr = float(fp / (fp + tn)) if (fp + tn) else float("nan")

    return {
        "auc": round(auc, 4) if auc == auc else None,
        "pr_auc": round(pr_auc, 4) if pr_auc == pr_auc else None,
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "fpr": round(fpr, 4) if fpr == fpr else None,
        "support": int(len(y_true)),
        "attack_support": int(y_true.sum()),
    }


def choose_threshold_f1(y_true: np.ndarray, scores: np.ndarray, fallback: float = 0.5) -> float:
    """只在验证集上按 F1 选阈值；没有可用的两类样本时退回人工阈值。"""
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    if len(np.unique(y_true)) < 2:
        return float(fallback)
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    if not len(thresholds):
        return float(fallback)
    f1 = (
        2
        * precision[:-1]
        * recall[:-1]
        / np.maximum(
            precision[:-1] + recall[:-1],
            1e-12,
        )
    )
    best = int(np.argmax(f1))
    return float(np.clip(thresholds[best], 0.0, 1.0))


def choose_threshold_fpr(
    y_true: np.ndarray,
    scores: np.ndarray,
    target_fpr: float,
    fallback: float = 0.5,
) -> float:
    """验证集上满足目标误报率时，选择召回率最高的阈值；测试集不参与。"""
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    if not 0 < target_fpr < 1:
        raise ValueError("target_fpr 应在 0~1 之间")
    if len(np.unique(y_true)) < 2:
        return float(fallback)
    fpr, tpr, thresholds = roc_curve(y_true, scores)
    eligible = np.flatnonzero(fpr <= target_fpr + 1e-12)
    if not len(eligible):
        return float(fallback)
    best = int(eligible[np.argmax(tpr[eligible])])
    return float(np.clip(thresholds[best], 0.0, 1.0))


def threshold_scan(y_true: np.ndarray, scores: np.ndarray, points: int = 11) -> list[dict]:
    """测试集阈值扫描，只用于展示部署权衡，不能拿来回选阈值。"""
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    rows = []
    for threshold in np.linspace(0.05, 0.95, points):
        metrics = compute_metrics(y_true, scores, threshold=float(threshold))
        rows.append(
            {
                "threshold": round(float(threshold), 2),
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "fpr": metrics["fpr"],
            }
        )
    return rows


def _indices(length: int, points: int) -> np.ndarray:
    if length <= points:
        return np.arange(length)
    return np.unique(np.linspace(0, length - 1, points, dtype=int))


def _finite(value: float) -> float | None:
    return round(float(value), 6) if np.isfinite(value) else None


def curve_data(
    y_true: np.ndarray,
    scores: np.ndarray,
    supervised: bool,
    points: int = 60,
) -> dict:
    """ROC/PR 曲线与概率校准；曲线点固定降采样，避免 payload 膨胀。"""
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    result = {
        "roc_curve": [],
        "pr_curve": [],
        "calibration": [],
        "brier_score": None,
        "calibration_note": (
            "监督模型输出概率，可参考校准曲线与 Brier score。"
            if supervised
            else "无监督模型输出异常分数，不是概率；不计算 Brier 与校准曲线。"
        ),
    }
    if len(np.unique(y_true)) < 2 or not len(y_true):
        return result

    fpr, tpr, thresholds = roc_curve(y_true, scores)
    roc_idx = _indices(len(fpr), points)
    result["roc_curve"] = [
        {
            "fpr": round(float(fpr[index]), 6),
            "tpr": round(float(tpr[index]), 6),
            "threshold": _finite(thresholds[index]),
        }
        for index in roc_idx
    ]

    precision, recall, pr_thresholds = precision_recall_curve(y_true, scores)
    usable = min(len(precision), len(recall), len(pr_thresholds))
    pr_idx = _indices(usable, points)
    result["pr_curve"] = [
        {
            "precision": round(float(precision[index]), 6),
            "recall": round(float(recall[index]), 6),
            "threshold": _finite(pr_thresholds[index]),
        }
        for index in pr_idx
    ]

    if supervised:
        try:
            prob_true, prob_pred = calibration_curve(
                y_true,
                scores,
                n_bins=min(10, max(3, len(y_true) // 50)),
                strategy="quantile",
            )
            result["calibration"] = [
                {
                    "mean_predicted": round(float(predicted), 6),
                    "fraction_positive": round(float(actual), 6),
                }
                for predicted, actual in zip(prob_pred, prob_true, strict=True)
            ]
            result["brier_score"] = round(float(brier_score_loss(y_true, scores)), 6)
        except ValueError:
            result["calibration_note"] += " 当前样本不足以计算稳定的分箱校准。"
    return result
