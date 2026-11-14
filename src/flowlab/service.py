"""实验编排：把"跑一次实验"收敛成一个函数。

CLI 与 API 都调它，避免两边各写一遍 run_experiment + ablation + payload。
"""

from __future__ import annotations

import shlex
from dataclasses import asdict, dataclass, field

import pandas as pd

from flowlab.eval.ablation import ablate as run_ablation
from flowlab.eval.runner import EvalResult, run_experiment
from flowlab.models.registry import available
from flowlab.payload import build_payload


@dataclass
class ExperimentSpec:
    models: list[str] = field(default_factory=lambda: ["mlp", "iforest", "autoencoder"])
    split: str = "temporal"
    test_size: float = 0.3
    seed: int = 42
    threshold: float = 0.5
    explain: bool = True
    ablate: str | None = None
    source_kind: str = "demo"
    source_ref: str | None = None
    normal: int = 5000
    attack: int = 500
    leaky: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def reproduction_command(spec: ExperimentSpec, effective_split: str) -> str:
    """生成能直接复现实验的命令，而不是无论来源都写 demo。"""
    common = [
        "--split",
        spec.split,
        "--test-size",
        str(spec.test_size),
        "--seed",
        str(spec.seed),
        "--threshold",
        str(spec.threshold),
        "--models",
        ",".join(spec.models),
    ]
    if spec.ablate:
        common += ["--ablate", spec.ablate]
    if spec.source_kind == "demo":
        args = [
            "uv",
            "run",
            "flowlab",
            "demo",
            "--normal",
            str(spec.normal),
            "--attack",
            str(spec.attack),
        ]
        if spec.leaky:
            args.append("--leaky")
        command = " ".join(shlex.quote(a) for a in args + common)
    else:
        source = spec.source_ref or "<data-file>"
        args = ["uv", "run", "flowlab", "run", source]
        command = " ".join(shlex.quote(a) for a in args + common)

    if spec.split == "temporal" and effective_split != "temporal":
        return "# 注意：原数据时间戳不足，实际使用分层随机切分\n" + command
    return command


def validate_spec(spec: ExperimentSpec) -> None:
    """在训练开始前拒绝明显无效的参数，CLI、API 与直接调用共用。"""
    if not spec.models:
        raise ValueError("至少选择一个模型")
    unknown = sorted({name for name in spec.models if name not in available()})
    if unknown:
        raise ValueError(f"未知模型 {unknown}，可用模型: {available()}")
    if not 0 <= spec.threshold <= 1:
        raise ValueError("threshold 应在 0~1 之间")
    if not 0.05 <= spec.test_size <= 0.5:
        raise ValueError("test_size 应在 0.05~0.5 之间")
    if not 0 <= spec.seed <= 2**32 - 1:
        raise ValueError("seed 应在 0~4294967295 之间")
    if spec.source_kind == "demo" and (spec.normal < 1 or spec.attack < 1):
        raise ValueError("合成数据的正常流与攻击流数量都必须大于 0")


def execute(df: pd.DataFrame, meta: dict, source: str, spec: ExperimentSpec) -> dict:
    """跑实验并返回统一 payload（含报告）。"""
    validate_spec(spec)
    spec.models = list(dict.fromkeys(spec.models))
    results, warns = run_experiment(
        df,
        models=spec.models,
        split=spec.split,
        seed=spec.seed,
        threshold=spec.threshold,
        test_size=spec.test_size,
        explain=spec.explain,
    )
    ablation = None
    if spec.ablate:
        used = results[0].features if results else []
        if spec.ablate not in used:
            raise ValueError(
                f"消融列 {spec.ablate!r} 没有参与训练，不能用于消融。可消融特征: {used[:15]}"
            )
        ablation = run_ablation(
            df,
            spec.ablate,
            models=spec.models,
            split=spec.split,
            seed=spec.seed,
            threshold=spec.threshold,
            test_size=spec.test_size,
        ).to_dict()
    meta = dict(meta)
    effective_split = results[0].split if results else spec.split
    experiment = spec.to_dict()
    experiment.update(
        {
            "source": source,
            "split_effective": effective_split,
            "command": reproduction_command(spec, effective_split),
        }
    )
    meta["experiment"] = experiment
    return build_payload(df, results, warns, source, meta, ablation=ablation)


def results_of(payload: dict) -> list[EvalResult]:
    return [
        r
        if isinstance(r, EvalResult)
        else EvalResult(**{k: v for k, v in r.items() if k in EvalResult.__dataclass_fields__})
        for r in payload.get("results", [])
    ]


def demo_frame(normal: int = 5000, attack: int = 500, seed: int = 42, leaky: bool = False):
    """合成数据 + 元信息，供 CLI/API 共用。"""
    from flowlab.engineer import add_engineered_features, describe
    from flowlab.schema import normalize_columns
    from flowlab.synthetic import generate

    df = add_engineered_features(
        normalize_columns(generate(n_normal=normal, n_attack=attack, seed=seed, leakage_only=leaky))
    )
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
        )
        if c in view.columns
    ]
    return (
        view.sort_values("score", ascending=False)
        .head(top)[cols + ["score"]]
        .round(4)
        .to_dict("records")
    )
