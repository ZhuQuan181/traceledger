"""实验执行器：一次跑多个模型，产出可复现的结果对象。"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

from flowlab.eval.metrics import compute_metrics
from flowlab.eval.split import plan_split
from flowlab.features.leakage import detect
from flowlab.features.prepare import build_matrix_pair
from flowlab.models.registry import available, create
from flowlab.schema import is_benign


def _missing_labels(labels: pd.Series) -> pd.Series:
    """空字符串、NaN 和常见空值写法都不能被悄悄当成攻击样本。"""
    normalized = labels.astype("string").str.strip().str.lower()
    return normalized.isna() | normalized.isin({"", "nan", "none", "null", "na", "n/a"})


def dataset_hash(df: pd.DataFrame) -> str:
    """内容哈希：同样的数据得到同样的 id，改一行就变。"""
    h = hashlib.sha256()
    h.update(",".join(map(str, df.columns)).encode())
    h.update(str(df.shape).encode())
    h.update(pd.util.hash_pandas_object(df, index=False).values.tobytes())
    return h.hexdigest()[:16]


def _json_safe(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat(sep=" ")
    if hasattr(value, "item"):
        return value.item()
    return value


def _detail_record(row: pd.Series, cols: list[str], score: float) -> dict:
    out = {key: _json_safe(row.get(key)) for key in cols}
    out["score"] = round(float(score), 4)
    return out


def _investigation_details(
    df: pd.DataFrame,
    test_idx: pd.Index,
    scores: np.ndarray,
    y_true: np.ndarray,
    threshold: float,
    label_col: str,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """构造按攻击类型、误报漏报和源 IP 的调查视图。"""
    te = df.loc[test_idx].copy()
    te["score"] = scores
    detail_cols = [
        c
        for c in (
            "src_ip",
            "dst_ip",
            "src_port",
            "dst_port",
            "protocol",
            "timestamp",
            "bytes_per_s",
            "packets_per_s",
            "fwd_packets",
            label_col,
        )
        if c in te.columns
    ]
    pred = scores >= threshold
    labels = (
        te[label_col] if label_col in te.columns else pd.Series(["—"] * len(te), index=te.index)
    )

    by_label: list[dict] = []
    for label, group in te.groupby(labels.rename("_label"), dropna=False, sort=False):
        positions = te.index.get_indexer(group.index)
        flagged = int(pred[positions].sum())
        kind = "benign" if is_benign(label) else "attack"
        by_label.append(
            {
                "label": "未知" if pd.isna(label) else str(label),
                "kind": kind,
                "total": int(len(group)),
                "flagged": flagged,
                "rate": round(flagged / len(group), 4) if len(group) else None,
            }
        )
    by_label.sort(key=lambda row: (row["kind"] == "benign", -row["total"]))

    false_positive_idx = te.index[(y_true == 0) & pred]
    false_negative_idx = te.index[(y_true == 1) & ~pred]
    false_positives = [
        _detail_record(te.loc[idx], detail_cols, te.loc[idx, "score"])
        for idx in te.loc[false_positive_idx].sort_values("score", ascending=False).head(8).index
    ]
    false_negatives = [
        _detail_record(te.loc[idx], detail_cols, te.loc[idx, "score"])
        for idx in te.loc[false_negative_idx].sort_values("score", ascending=False).head(8).index
    ]

    source_ranking: list[dict] = []
    if "src_ip" in te.columns:
        alerts = te.loc[pred].copy()
        if not alerts.empty:
            alerts["_true_attack"] = y_true[pred]
            grouped = (
                alerts.groupby("src_ip", dropna=False)
                .agg(
                    alerts=("score", "size"),
                    true_attacks=("_true_attack", "sum"),
                    max_score=("score", "max"),
                )
                .reset_index()
            )
            grouped["false_alarms"] = grouped["alerts"] - grouped["true_attacks"]
            grouped = grouped.sort_values(["true_attacks", "alerts"], ascending=False).head(10)
            source_ranking = [
                {
                    "src_ip": str(row["src_ip"]),
                    "alerts": int(row["alerts"]),
                    "true_attacks": int(row["true_attacks"]),
                    "false_alarms": int(row["false_alarms"]),
                    "max_score": round(float(row["max_score"]), 4),
                }
                for _, row in grouped.iterrows()
            ]
    return by_label, false_positives, false_negatives, source_ranking


@dataclass
class EvalResult:
    model: str
    kind: str
    metrics: dict
    confusion: dict
    duration_s: float
    params: dict = field(default_factory=dict)
    split: str = "temporal"
    split_requested: str = "temporal"
    dataset_hash: str = ""
    n_train: int = 0
    n_test: int = 0
    threshold: float = 0.5
    top_flows: list[dict] = field(default_factory=list)
    score_curve: list[dict] = field(default_factory=list)
    by_label: list[dict] = field(default_factory=list)
    false_positives: list[dict] = field(default_factory=list)
    false_negatives: list[dict] = field(default_factory=list)
    source_ranking: list[dict] = field(default_factory=list)
    seed: int = 42
    attack_train: int = 0
    features: list[str] = field(default_factory=list)
    encoded_features: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def run_experiment(
    df: pd.DataFrame,
    models: list[str] | None = None,
    split: str = "temporal",
    test_size: float = 0.3,
    seed: int = 42,
    threshold: float = 0.5,
    label_col: str = "label",
    explain: bool = False,
    top_k: int = 20,
) -> tuple[list[EvalResult], list[dict]]:
    if models is None:
        models = ["mlp", "iforest", "autoencoder"]
    models = list(dict.fromkeys(models))
    if not models:
        raise ValueError("至少选择一个模型")
    unknown = sorted({name for name in models if name not in available()})
    if unknown:
        raise ValueError(f"未知模型 {unknown}，可用模型: {available()}")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold 应在 0~1 之间")
    if label_col not in df.columns:
        raise ValueError(
            f"缺少标签列 {label_col!r}。评估需要每条流都有标签；"
            "请补齐 label 列或提供能完整对齐的旁挂标签。"
        )
    missing = _missing_labels(df[label_col])
    if missing.any():
        examples = df.loc[missing, label_col].head(3).astype(str).tolist()
        raise ValueError(
            f"标签列有 {int(missing.sum())} 行缺失或为空（示例: {examples}）。"
            "未标注的流不能被当作攻击样本；请补齐标签或先过滤这些行。"
        )

    plan = plan_split(df, mode=split, test_size=test_size, seed=seed, label_col=label_col)
    warns = detect(df, split=plan.effective, label_col=label_col)
    test_labels = df.loc[plan.test, label_col].map(is_benign)
    if test_labels.all() or not test_labels.any():
        raise ValueError(
            "测试集必须同时包含 BENIGN 和攻击样本，否则无法计算 AUC、召回率与误报率。"
            "请调整测试集比例或切分方式，或改用 `flowlab score` 做无监督排序。"
        )
    if plan.fell_back:
        warns.insert(
            0,
            {
                "rule": "temporal_fallback",
                "columns": [],
                "severity": "high",
                "message": plan.warnings[0],
                "suggestion": "补齐可解析的时间戳后重跑；否则把结论明确标成随机切分，不能声称时间外推。",
            },
        )
    elif plan.warnings:
        warns.insert(
            0,
            {
                "rule": "split_coverage",
                "columns": [],
                "severity": "high",
                "message": " ".join(plan.warnings),
                "suggestion": "检查攻击样本在时间上的分布，调整 test_size 或先修正数据切分。",
            },
        )
    dh = dataset_hash(df)

    train_idx, test_idx = plan.train, plan.test
    prep_tr, prep_te = build_matrix_pair(df.loc[train_idx], df.loc[test_idx], label_col=label_col)

    if (prep_tr.y == 1).sum() == 0 and any(create(n).kind == "supervised" for n in models):
        raise ValueError(
            "训练集里没有攻击样本，监督模型无法学习。"
            "请调整 --test-size、改用 --split random，或检查数据的时间分布。"
        )

    results: list[EvalResult] = []
    for name in models:
        t0 = time.perf_counter()
        det = create(name)
        det.fit(prep_tr.X, prep_tr.y)
        scores = det.score(prep_te.X)
        metrics = compute_metrics(prep_te.y, scores, threshold=threshold)
        cm = confusion_matrix(prep_te.y, (scores >= threshold).astype(int), labels=[0, 1]).ravel()

        top_flows: list[dict] = []
        score_curve: list[dict] = []
        by_label: list[dict] = []
        false_positives: list[dict] = []
        false_negatives: list[dict] = []
        source_ranking: list[dict] = []
        if explain:
            te = df.loc[test_idx].copy()
            te["score"] = scores
            cols = [
                c
                for c in (
                    "src_ip",
                    "dst_ip",
                    "dst_port",
                    "protocol",
                    "timestamp",
                    "bytes_per_s",
                    "packets_per_s",
                    "fwd_packets",
                    label_col,
                )
                if c in te.columns
            ]
            top = te.sort_values("score", ascending=False).head(top_k)
            arr = np.asarray(scores, dtype=float)
            buckets = np.array_split(arr, min(90, max(20, len(arr) // 12)))
            # p = 该时间窗内的最高分（用来定高度），h = 超过阈值的比例（用来定红色浓度）
            score_curve = [
                {"p": round(float(np.max(b)), 3), "h": round(float((b >= threshold).mean()), 3)}
                if len(b)
                else {"p": 0.0, "h": 0.0}
                for b in buckets
            ]

            top_flows = [
                {
                    **{k: _json_safe(v) for k, v in row.items()},
                    "score": round(float(row["score"]), 4),
                }
                for row in top[cols + ["score"]].to_dict("records")
            ]
            by_label, false_positives, false_negatives, source_ranking = _investigation_details(
                df, test_idx, np.asarray(scores), prep_te.y, threshold, label_col
            )
        results.append(
            EvalResult(
                model=name,
                kind=det.kind,
                metrics=metrics,
                confusion={"tn": int(cm[0]), "fp": int(cm[1]), "fn": int(cm[2]), "tp": int(cm[3])},
                duration_s=round(time.perf_counter() - t0, 3),
                params=det.info().get("params", {}),
                split=plan.effective,
                split_requested=split,
                dataset_hash=dh,
                n_train=int(len(prep_tr.X)),
                n_test=int(len(prep_te.X)),
                threshold=threshold,
                top_flows=top_flows,
                score_curve=score_curve,
                by_label=by_label,
                false_positives=false_positives,
                false_negatives=false_negatives,
                source_ranking=source_ranking,
                seed=seed,
                attack_train=int((prep_tr.y == 1).sum()),
                features=list(prep_tr.raw_features),
                encoded_features=len(prep_tr.feature_names),
            )
        )
    return results, warns
