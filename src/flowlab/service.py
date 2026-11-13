"""实验编排：把"跑一次实验"收敛成一个函数。

CLI 与 API 都调它，避免两边各写一遍 run_experiment + ablation + payload。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from flowlab.eval.ablation import ablate as run_ablation
from flowlab.eval.runner import EvalResult, run_experiment
from flowlab.payload import build_payload


@dataclass
class ExperimentSpec:
    models: list[str] = field(default_factory=lambda: ["mlp", "iforest", "autoencoder"])
    split: str = "temporal"
    seed: int = 42
    threshold: float = 0.5
    explain: bool = True
    ablate: str | None = None


def execute(df: pd.DataFrame, meta: dict, source: str, spec: ExperimentSpec) -> dict:
    """跑实验并返回统一 payload（含报告）。"""
    results, warns = run_experiment(df, models=spec.models, split=spec.split,
                                    seed=spec.seed, threshold=spec.threshold,
                                    explain=spec.explain)
    ablation = None
    if spec.ablate:
        ablation = run_ablation(df, spec.ablate, models=spec.models, split=spec.split,
                                seed=spec.seed, threshold=spec.threshold).to_dict()
    return build_payload(df, results, warns, source, meta, ablation=ablation)


def results_of(payload: dict) -> list[EvalResult]:
    return [r if isinstance(r, EvalResult) else EvalResult(
        **{k: v for k, v in r.items() if k in EvalResult.__dataclass_fields__})
        for r in payload.get("results", [])]


def demo_frame(normal: int = 5000, attack: int = 500, seed: int = 42,
               leaky: bool = False):
    """合成数据 + 元信息，供 CLI/API 共用。"""
    from flowlab.engineer import add_engineered_features, describe
    from flowlab.schema import normalize_columns
    from flowlab.synthetic import generate

    df = add_engineered_features(
        normalize_columns(generate(n_normal=normal, n_attack=attack, seed=seed, leakage_only=leaky)))
    meta = {
        "engineering": describe(),
        "labels": {"mode": "embedded", "labelled": len(df), "total": len(df)},
        "format": {"format": "synthetic", "shape": f"{len(df)} 行"},
    }
    source = "合成数据（端口泄漏版）" if leaky else "合成数据"
    return df, meta, source


def score_frame(df: pd.DataFrame, model: str = "iforest", top: int = 20) -> list[dict]:
    """无标签数据打分：返回最可疑的 N 条流（含分数）。"""
    from flowlab.features.prepare import build_feature_matrix
    from flowlab.models.registry import create

    X, feats = build_feature_matrix(df)
    det = create(model)
    det.fit(X, None)
    view = df.copy()
    view["score"] = det.score(X)
    cols = [c for c in ("src_ip", "dst_ip", "dst_port", "protocol", "timestamp",
                        "bytes_per_s", "packets_per_s") if c in view.columns]
    return view.sort_values("score", ascending=False).head(top)[cols + ["score"]] \
               .round(4).to_dict("records")
