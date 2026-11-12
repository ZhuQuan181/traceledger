"""实验执行器：一次跑多个模型，产出可复现的结果对象。"""
from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field

import pandas as pd
from sklearn.metrics import confusion_matrix

from flowlab.eval.metrics import compute_metrics
from flowlab.eval.split import split_indices
from flowlab.features.leakage import detect
from flowlab.features.prepare import build_matrix_pair
from flowlab.models.registry import create


def dataset_hash(df: pd.DataFrame) -> str:
    """内容哈希：同样的数据得到同样的 id，改一行就变。"""
    h = hashlib.sha256()
    h.update(",".join(map(str, df.columns)).encode())
    h.update(str(df.shape).encode())
    h.update(pd.util.hash_pandas_object(df, index=False).values.tobytes())
    return h.hexdigest()[:16]


@dataclass
class EvalResult:
    model: str
    kind: str
    metrics: dict
    confusion: dict
    duration_s: float
    params: dict = field(default_factory=dict)
    split: str = "temporal"
    dataset_hash: str = ""
    n_train: int = 0
    n_test: int = 0
    threshold: float = 0.5
    top_flows: list[dict] = field(default_factory=list)
    score_curve: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def run_experiment(df: pd.DataFrame, models: list[str] | None = None,
                   split: str = "temporal", test_size: float = 0.3,
                   seed: int = 42, threshold: float = 0.5,
                   label_col: str = "label", explain: bool = False,
                   top_k: int = 20) -> tuple[list[EvalResult], list[dict]]:
    models = models or ["mlp", "iforest", "autoencoder"]
    warns = detect(df, split=split, label_col=label_col)
    dh = dataset_hash(df)

    train_idx, test_idx = split_indices(df, mode=split, test_size=test_size, seed=seed,
                                       label_col=label_col)
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
        if explain:
            te = df.loc[test_idx].copy()
            te["score"] = scores
            cols = [c for c in ("src_ip", "dst_ip", "dst_port", "protocol", "timestamp",
                                "bytes_per_s", "packets_per_s", "fwd_packets", label_col)
                    if c in te.columns]
            top = te.sort_values("score", ascending=False).head(top_k)
            import numpy as _np
            arr = _np.asarray(scores, dtype=float)
            buckets = _np.array_split(arr, min(200, max(20, len(arr) // 5)))
            # p = 该时间窗内的最高分（用来定高度），h = 超过阈值的比例（用来定红色浓度）
            score_curve = [
                {"p": round(float(_np.max(b)), 3), "h": round(float((b >= threshold).mean()), 3)}
                if len(b) else {"p": 0.0, "h": 0.0}
                for b in buckets
            ]

            top_flows = [
                {**{k: (None if pd.isna(v) else v) for k, v in row.items()},
                 "score": round(float(row["score"]), 4)}
                for row in top[cols + ["score"]].to_dict("records")
            ]
        results.append(
            EvalResult(
                model=name, kind=det.kind, metrics=metrics,
                confusion={"tn": int(cm[0]), "fp": int(cm[1]), "fn": int(cm[2]), "tp": int(cm[3])},
                duration_s=round(time.perf_counter() - t0, 3),
                params=det.info().get("params", {}), split=split, dataset_hash=dh,
                n_train=int(len(prep_tr.X)), n_test=int(len(prep_te.X)), threshold=threshold,
                top_flows=top_flows, score_curve=score_curve,
            )
        )
    return results, warns
