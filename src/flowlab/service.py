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
