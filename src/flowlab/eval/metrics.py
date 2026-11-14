"""指标计算：ROC-AUC / PR-AUC / F1 / 精确率 / 召回率 / 误报率 / 混淆矩阵。"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
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
