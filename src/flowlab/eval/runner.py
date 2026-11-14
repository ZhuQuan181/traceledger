"""实验执行器：一次跑多个模型，产出可复现的结果对象。"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

from flowlab.eval.metrics import (
    choose_threshold_f1,
    choose_threshold_fpr,
    compute_metrics,
    curve_data,
    threshold_scan,
)
from flowlab.eval.split import plan_split
from flowlab.features.leakage import detect
from flowlab.features.prepare import build_matrix_splits
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
    validation_metrics: dict = field(default_factory=dict)
    validation_confusion: dict = field(default_factory=dict)
    selection_rule: str = "validation_auc"
    params: dict = field(default_factory=dict)
    split: str = "temporal"
    split_requested: str = "temporal"
    dataset_hash: str = ""
    n_train: int = 0
    n_validation: int = 0
    n_test: int = 0
    threshold: float = 0.5
    threshold_source: str = "fixed"
    threshold_target_fpr: float | None = None
    top_flows: list[dict] = field(default_factory=list)
    score_curve: list[dict] = field(default_factory=list)
    score_curve_basis: str = "order"
    threshold_scan: list[dict] = field(default_factory=list)
    roc_curve: list[dict] = field(default_factory=list)
    pr_curve: list[dict] = field(default_factory=list)
    calibration: list[dict] = field(default_factory=list)
    brier_score: float | None = None
    calibration_note: str = ""
    by_label: list[dict] = field(default_factory=list)
    false_positives: list[dict] = field(default_factory=list)
    false_negatives: list[dict] = field(default_factory=list)
    source_ranking: list[dict] = field(default_factory=list)
    seed: int = 42
    attack_train: int = 0
    attack_validation: int = 0
    features: list[str] = field(default_factory=list)
    encoded_features: int = 0
    split_diagnostics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def selection_auc(result: EvalResult) -> float | None:
    """模型选择只看验证集；旧历史没有验证指标时才退回测试集。"""
    value = (result.validation_metrics or {}).get("auc")
    if value is not None:
        return float(value)
    return result.metrics.get("auc")


def select_best(results: list[EvalResult]) -> EvalResult | None:
    """按验证集 AUC 选模型，测试集不参与选择。"""
    if not results:
        return None

    def _rank(result: EvalResult) -> float:
        value = selection_auc(result)
        return float("-inf") if value is None else value

    return max(results, key=_rank)


def _create_detector(name: str, seed: int):
    """把实验种子传给模型；兼容不接受 seed 参数的第三方插件。"""
    try:
        return create(name, seed=seed)
    except TypeError as exc:
        if "seed" not in str(exc):
            raise
        return create(name)


def run_experiment(
    df: pd.DataFrame,
    models: list[str] | None = None,
    split: str = "temporal",
    test_size: float = 0.3,
    validation_size: float = 0.2,
    seed: int = 42,
    threshold: float = 0.5,
    threshold_mode: str = "fixed",
    target_fpr: float = 0.01,
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
    if threshold_mode not in {"fixed", "f1", "fpr"}:
        raise ValueError("threshold_mode 只能是 fixed、f1 或 fpr")
    if not 0 < target_fpr < 1:
        raise ValueError("target_fpr 应在 0~1 之间")
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

    plan = plan_split(
        df,
        mode=split,
        test_size=test_size,
        validation_size=validation_size,
        seed=seed,
        label_col=label_col,
    )
    warns = detect(df, split=plan.effective, label_col=label_col)
    validation_labels = df.loc[plan.validation, label_col].map(is_benign)
    test_labels = df.loc[plan.test, label_col].map(is_benign)
    if validation_labels.all() or not validation_labels.any():
        raise ValueError(
            "验证集必须同时包含 BENIGN 和攻击样本，否则无法在不读取测试集的情况下选择模型。"
            "请调整切分比例或切分方式，或增加样本量。"
        )
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
    else:
        coverage_messages = [
            message
            for message in plan.warnings
            if "实体同时出现在多个子集中" not in message and "完全重复内容" not in message
        ]
        if coverage_messages:
            warns.insert(
                0,
                {
                    "rule": "split_coverage",
                    "columns": [],
                    "severity": "high",
                    "message": " ".join(coverage_messages),
                    "suggestion": "检查攻击样本在时间上的分布，调整 test_size 或先修正数据切分。",
                },
            )
    diagnostics = plan.diagnostics or {}
    duplicate_cross = diagnostics.get("duplicate_cross") or {}
    if any(duplicate_cross.values()):
        warns.append(
            {
                "rule": "duplicate_leak",
                "columns": [],
                "severity": "high",
                "message": "训练/验证/测试之间存在完全重复内容，重复样本会同时抬高验证与测试指标。",
                "suggestion": "先去重；若要评估泛化能力，改用 --split group 按实体切分。",
            }
        )
    entity_overlap = diagnostics.get("entity_overlap") or {}
    if plan.effective != "group" and any(entity_overlap.values()):
        warns.append(
            {
                "rule": "entity_overlap",
                "columns": [],
                "severity": "medium",
                "message": (
                    f"按 {diagnostics.get('entity_key')} 统计，同一实体出现在多个子集中；"
                    "指标衡量的是同分布拟合，不是新主机/新会话泛化。"
                ),
                "suggestion": "若研究目标是泛化到未见实体，改用 --split group。",
            }
        )
    dh = dataset_hash(df)

    train_idx, validation_idx, test_idx = plan.train, plan.validation, plan.test
    prep_tr, prep_val, prep_te = build_matrix_splits(
        df.loc[train_idx],
        df.loc[validation_idx],
        df.loc[test_idx],
        label_col=label_col,
    )

    if (prep_tr.y == 1).sum() == 0 and any(create(n).kind == "supervised" for n in models):
        raise ValueError(
            "训练集里没有攻击样本，监督模型无法学习。"
            "请调整 --test-size、改用 --split random，或检查数据的时间分布。"
        )

    results: list[EvalResult] = []
    for name in models:
        t0 = time.perf_counter()
        det = _create_detector(name, seed)
        det.fit(prep_tr.X, prep_tr.y)
        validation_scores = det.score(prep_val.X)
        scores = det.score(prep_te.X)
        if threshold_mode == "f1":
            chosen_threshold = choose_threshold_f1(
                prep_val.y, validation_scores, fallback=threshold
            )
        elif threshold_mode == "fpr":
            chosen_threshold = choose_threshold_fpr(
                prep_val.y,
                validation_scores,
                target_fpr=target_fpr,
                fallback=threshold,
            )
        else:
            chosen_threshold = threshold
        validation_metrics = compute_metrics(
            prep_val.y, validation_scores, threshold=chosen_threshold
        )
        metrics = compute_metrics(prep_te.y, scores, threshold=chosen_threshold)
        validation_cm = confusion_matrix(
            prep_val.y, (validation_scores >= chosen_threshold).astype(int), labels=[0, 1]
        ).ravel()
        cm = confusion_matrix(
            prep_te.y, (scores >= chosen_threshold).astype(int), labels=[0, 1]
        ).ravel()
        scan = threshold_scan(prep_te.y, scores)
        curves = curve_data(prep_te.y, scores, supervised=det.kind == "supervised")

        top_flows: list[dict] = []
        score_curve: list[dict] = []
        curve_basis = "order"
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
            if plan.effective == "temporal" and "timestamp" in te.columns:
                timestamps = pd.to_datetime(te["timestamp"], errors="coerce", format="mixed")
                if timestamps.notna().any():
                    ordered_index = timestamps.sort_values(kind="mergesort").index
                    arr = pd.Series(arr, index=te.index).loc[ordered_index].to_numpy()
                    curve_basis = "time"
            buckets = np.array_split(arr, min(90, max(20, len(arr) // 12)))
            # p = 该时间窗内的最高分（用来定高度），h = 超过阈值的比例（用来定红色浓度）
            score_curve = [
                {
                    "p": round(float(np.max(b)), 3),
                    "h": round(float((b >= chosen_threshold).mean()), 3),
                }
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
                df,
                test_idx,
                np.asarray(scores),
                prep_te.y,
                chosen_threshold,
                label_col,
            )
        results.append(
            EvalResult(
                model=name,
                kind=det.kind,
                metrics=metrics,
                confusion={"tn": int(cm[0]), "fp": int(cm[1]), "fn": int(cm[2]), "tp": int(cm[3])},
                duration_s=round(time.perf_counter() - t0, 3),
                validation_metrics=validation_metrics,
                validation_confusion={
                    "tn": int(validation_cm[0]),
                    "fp": int(validation_cm[1]),
                    "fn": int(validation_cm[2]),
                    "tp": int(validation_cm[3]),
                },
                params=det.info().get("params", {}),
                split=plan.effective,
                split_requested=split,
                dataset_hash=dh,
                n_train=int(len(prep_tr.X)),
                n_validation=int(len(prep_val.X)),
                n_test=int(len(prep_te.X)),
                threshold=round(float(chosen_threshold), 4),
                threshold_source=(
                    "validation_f1"
                    if threshold_mode == "f1"
                    else "validation_fpr"
                    if threshold_mode == "fpr"
                    else "fixed"
                ),
                threshold_target_fpr=(target_fpr if threshold_mode == "fpr" else None),
                top_flows=top_flows,
                score_curve=score_curve,
                threshold_scan=scan,
                roc_curve=curves["roc_curve"],
                pr_curve=curves["pr_curve"],
                calibration=curves["calibration"],
                brier_score=curves["brier_score"],
                calibration_note=curves["calibration_note"],
                score_curve_basis=curve_basis,
                by_label=by_label,
                false_positives=false_positives,
                false_negatives=false_negatives,
                source_ranking=source_ranking,
                seed=seed,
                attack_train=int((prep_tr.y == 1).sum()),
                attack_validation=int((prep_val.y == 1).sum()),
                features=list(prep_tr.raw_features),
                encoded_features=len(prep_tr.feature_names),
                split_diagnostics=diagnostics,
            )
        )
    return results, warns
