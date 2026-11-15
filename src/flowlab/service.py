"""实验编排：把"跑一次实验"收敛成一个函数。

CLI 与 API 都调它，避免两边各写一遍 run_experiment + ablation + payload。
"""

from __future__ import annotations

import shlex
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import pandas as pd

from flowlab.errors import ExperimentCancelled
from flowlab.eval.ablation import ablate as run_ablation
from flowlab.eval.runner import EvalResult, run_experiment
from flowlab.models.registry import available
from flowlab.payload import build_payload

ProgressCallback = Callable[[str, int, int], None]
CancelCallback = Callable[[], bool]


def _notify(progress: ProgressCallback | None, phase: str, completed: int, total: int) -> None:
    if progress is not None:
        progress(phase, completed, total)


def _check_cancel(cancel: CancelCallback | None) -> None:
    if cancel is not None and cancel():
        raise ExperimentCancelled


@dataclass
class ExperimentSpec:
    models: list[str] = field(default_factory=lambda: ["mlp", "iforest", "autoencoder"])
    split: str = "temporal"
    test_size: float = 0.3
    validation_size: float = 0.2
    seed: int = 42
    threshold: float = 0.5
    threshold_mode: str = "fixed"
    target_fpr: float = 0.01
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
        "--validation-size",
        str(spec.validation_size),
        "--seed",
        str(spec.seed),
        "--threshold",
        str(spec.threshold),
        "--threshold-mode",
        spec.threshold_mode,
    ]
    if spec.threshold_mode == "fpr":
        common += ["--target-fpr", str(spec.target_fpr)]
    common += ["--models", ",".join(spec.models)]
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
    if spec.threshold_mode not in {"fixed", "f1", "fpr"}:
        raise ValueError("threshold_mode 只能是 fixed、f1 或 fpr")
    if not 0 < spec.target_fpr < 1:
        raise ValueError("target_fpr 应在 0~1 之间")
    if not 0.05 <= spec.test_size <= 0.5:
        raise ValueError("test_size 应在 0.05~0.5 之间")
    if not 0.05 <= spec.validation_size <= 0.4:
        raise ValueError("validation_size 应在 0.05~0.4 之间")
    if spec.test_size + spec.validation_size > 0.8:
        raise ValueError("test_size + validation_size 不能超过 0.8")
    if not 0 <= spec.seed <= 2**32 - 1:
        raise ValueError("seed 应在 0~4294967295 之间")
    if spec.source_kind == "demo" and (spec.normal < 1 or spec.attack < 1):
        raise ValueError("合成数据的正常流与攻击流数量都必须大于 0")


def execute(
    df: pd.DataFrame,
    meta: dict,
    source: str,
    spec: ExperimentSpec,
    *,
    progress: ProgressCallback | None = None,
    cancel: CancelCallback | None = None,
) -> dict:
    """跑实验并返回统一 payload（含报告）。"""
    _check_cancel(cancel)
    _notify(progress, "validating", 0, 1)
    validate_spec(spec)
    _notify(progress, "validating", 1, 1)
    _check_cancel(cancel)
    spec.models = list(dict.fromkeys(spec.models))
    results, warns = run_experiment(
        df,
        models=spec.models,
        split=spec.split,
        seed=spec.seed,
        threshold=spec.threshold,
        threshold_mode=spec.threshold_mode,
        target_fpr=spec.target_fpr,
        test_size=spec.test_size,
        validation_size=spec.validation_size,
        explain=spec.explain,
        progress=progress,
        cancel=cancel,
    )
    ablation = None
    if spec.ablate:
        used = results[0].features if results else []
        if spec.ablate not in used:
            raise ValueError(
                f"消融列 {spec.ablate!r} 没有参与训练，不能用于消融。可消融特征: {used[:15]}"
            )
        _notify(progress, "ablation", 0, len(spec.models))
        ablation = run_ablation(
            df,
            spec.ablate,
            models=spec.models,
            split=spec.split,
            seed=spec.seed,
            threshold=spec.threshold,
            threshold_mode=spec.threshold_mode,
            target_fpr=spec.target_fpr,
            test_size=spec.test_size,
            validation_size=spec.validation_size,
            base_results=results,
            progress=progress,
            cancel=cancel,
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
    _notify(progress, "report", 0, 1)
    _check_cancel(cancel)
    payload = build_payload(df, results, warns, source, meta, ablation=ablation)
    _notify(progress, "report", 1, 1)
    return payload


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


def _score_value(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "isoformat"):
        return value.isoformat(sep=" ") if isinstance(value, pd.Timestamp) else value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def score_frame(
    df: pd.DataFrame,
    model: str = "iforest",
    top: int = 20,
    *,
    progress: ProgressCallback | None = None,
    cancel: CancelCallback | None = None,
) -> list[dict]:
    """无标签数据打分：返回最可疑的 N 条流（含分数）。"""
    from flowlab.features.prepare import build_feature_matrix
    from flowlab.models.registry import available, create

    _check_cancel(cancel)
    if model not in available():
        raise ValueError(f"未知模型 {model!r}，可用模型: {available()}")
    detector = create(model)
    if detector.kind != "unsupervised":
        raise ValueError("无标签打分只能使用无监督模型（iforest / autoencoder）")
    if not 1 <= top <= 500:
        raise ValueError("top 应在 1~500 之间")

    _notify(progress, "features", 0, 1)
    X, _ = build_feature_matrix(df)
    _notify(progress, "features", 1, 1)
    _check_cancel(cancel)
    _notify(progress, "model", 0, 1)
    detector.fit(X, None)
    _check_cancel(cancel)
    scores = detector.score(X)
    _notify(progress, "model", 1, 1)
    _check_cancel(cancel)
    view = df.copy()
    view["score"] = scores
    cols = [
        c
        for c in (
            "src_ip",
            "dst_ip",
            "src_port",
            "dst_port",
            "protocol",
            "timestamp",
            "duration_ms",
            "fwd_packets",
            "bwd_packets",
            "fwd_bytes",
            "bwd_bytes",
            "bytes_per_s",
            "packets_per_s",
        )
        if c in view.columns
    ]
    rows = (
        view.sort_values("score", ascending=False)
        .assign(
            **{column: view[column].map(_score_value) for column in cols if column != "timestamp"}
        )
        .head(top)[cols + ["score"]]
        .to_dict("records")
    )
    return [
        {
            **{key: _score_value(value) for key, value in row.items()},
            "score": round(float(row["score"]), 4),
        }
        for row in rows
    ]


def score_payload(
    df: pd.DataFrame,
    meta: dict,
    source: str,
    *,
    model: str = "iforest",
    top: int = 50,
    progress: ProgressCallback | None = None,
    cancel: CancelCallback | None = None,
) -> dict:
    """无标签排序的 API payload：不生成评估指标，也不伪装成一次监督实验。"""
    _check_cancel(cancel)
    rows = score_frame(
        df,
        model=model,
        top=top,
        progress=progress,
        cancel=cancel,
    )
    scores = [float(row["score"]) for row in rows]
    _notify(progress, "report", 0, 1)
    _check_cancel(cancel)
    from flowlab.eval.runner import dataset_hash

    payload = {
        "mode": "score",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source": source,
        "dataset": {
            "source": source,
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "hash": dataset_hash(df),
            "format": meta.get("format", {}),
            "labels": meta.get("labels"),
        },
        "model": {"name": model, "kind": "unsupervised"},
        "top": rows,
        "summary": {
            "returned": len(rows),
            "scored_rows": int(len(df)),
            "max_score": max(scores) if scores else None,
            "median_top_score": (round(float(pd.Series(scores).median()), 4) if scores else None),
            "p95_top_score": (
                round(float(pd.Series(scores).quantile(0.95)), 4) if scores else None
            ),
        },
        "note": "无标签模式只做可疑度排序，不计算 AUC、F1 或误报率。",
    }
    _notify(progress, "report", 1, 1)
    return payload
