"""指标计算：AUC / F1 / 精确率 / 召回率 / 误报率 / 混淆矩阵。"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)


def compute_metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float = 0.5) -> dict:
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    y_pred = (scores >= threshold).astype(int)

    try:
        auc = float(roc_auc_score(y_true, scores)) if len(np.unique(y_true)) > 1 else float("nan")
    except ValueError:
        auc = float("nan")

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    fpr = float(fp / (fp + tn)) if (fp + tn) else float("nan")

    return {
        "auc": round(auc, 4) if auc == auc else None,
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "fpr": round(fpr, 4) if fpr == fpr else None,
        "support": int(len(y_true)),
        "attack_support": int(y_true.sum()),
    }
