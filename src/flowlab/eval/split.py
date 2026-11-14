"""切分策略：默认时间切分，避免未来信息泄漏。"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import pandas as pd

from flowlab.schema import is_benign, normalize_name


@dataclass
class SplitPlan:
    train: pd.Index
    test: pd.Index
    requested: str
    effective: str
    warnings: list[str] = field(default_factory=list)

    @property
    def fell_back(self) -> bool:
        return self.requested == "temporal" and self.effective != "temporal"


def _timestamp_series(df: pd.DataFrame) -> pd.Series | None:
    for col in df.columns:
        if normalize_name(col) == "timestamp":
            return pd.to_datetime(df[col], errors="coerce", format="mixed")
    return None


def _coverage_warnings(
    df: pd.DataFrame, train: pd.Index, test: pd.Index, label_col: str
) -> list[str]:
    if label_col not in df.columns:
        return []
    out: list[str] = []
    for name, idx in (("训练集", train), ("测试集", test)):
        attack_count = (~df.loc[idx, label_col].map(is_benign)).sum()
        if attack_count == 0:
            out.append(
                f"{name}中没有攻击样本（{len(idx)} 行全为 BENIGN）。"
                "时间切分下这通常意味着攻击集中在某个时段，建议调整 test_size 或改用分层时间切分。"
            )
    return out


def plan_split(
    df: pd.DataFrame,
    mode: str = "temporal",
    test_size: float = 0.3,
    seed: int = 42,
    label_col: str = "label",
) -> SplitPlan:
    """返回切分计划，并明确记录最终使用的模式。

    temporal: 按时间排序，前 (1-test_size) 训练；时间不可解析时退化为 random。
    random:   分层随机切分（仅在你确认数据无时间相关性时使用）。
    """
    if mode not in {"temporal", "random"}:
        raise ValueError("split 只能是 temporal 或 random")
    if not 0.05 <= test_size <= 0.5:
        raise ValueError("test_size 应在 0.05~0.5 之间")
    if len(df) < 20:
        raise ValueError("样本太少（<20 行），无法切分")

    ts = _timestamp_series(df) if mode == "temporal" else None
    effective = mode
    split_warnings: list[str] = []
    if ts is not None and ts.notna().sum() >= len(df) * 0.9:
        order = ts.sort_values(kind="mergesort").index
        cut = int(len(order) * (1 - test_size))
        train, test = pd.Index(order[:cut]), pd.Index(order[cut:])
    else:
        if mode == "temporal":
            effective = "random"
            split_warnings.append(
                "请求了时间切分，但时间戳缺失或可解析比例不足 90%，"
                "已退化为分层随机切分；这组指标不再具备时间外推含义。"
            )
        from sklearn.model_selection import train_test_split

        stratify = (
            df[label_col] if label_col in df.columns and df[label_col].nunique() > 1 else None
        )
        tr, te = train_test_split(
            df.index, test_size=test_size, random_state=seed, stratify=stratify
        )
        train, test = pd.Index(tr), pd.Index(te)

    split_warnings.extend(_coverage_warnings(df, train, test, label_col))
    return SplitPlan(
        train=train, test=test, requested=mode, effective=effective, warnings=split_warnings
    )


def split_indices(
    df: pd.DataFrame,
    mode: str = "temporal",
    test_size: float = 0.3,
    seed: int = 42,
    label_col: str = "label",
) -> tuple[pd.Index, pd.Index]:
    """兼容旧调用的二元组接口；需要切分诊断时用 plan_split。"""
    plan = plan_split(df, mode=mode, test_size=test_size, seed=seed, label_col=label_col)
    for message in plan.warnings:
        warnings.warn(message, RuntimeWarning, stacklevel=2)
    return plan.train, plan.test
