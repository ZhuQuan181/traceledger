"""切分策略：默认时间切分，避免未来信息泄漏。"""
from __future__ import annotations

import warnings

import pandas as pd

from flowlab.schema import normalize_name

BENIGN = "benign"


def _timestamp_series(df: pd.DataFrame) -> pd.Series | None:
    for col in df.columns:
        if normalize_name(col) == "timestamp":
            return pd.to_datetime(df[col], errors="coerce", format="mixed")
    return None


def _coverage_warnings(df: pd.DataFrame, train: pd.Index, test: pd.Index, label_col: str) -> None:
    if label_col not in df.columns:
        return
    for name, idx in (("训练集", train), ("测试集", test)):
        labs = df.loc[idx, label_col].astype(str).str.strip().str.lower()
        if (labs != BENIGN).sum() == 0:
            warnings.warn(
                f"{name}中没有攻击样本（{len(idx)} 行全为 BENIGN）。"
                "时间切分下这通常意味着攻击集中在某个时段，建议调整 test_size 或改用分层时间切分。",
                RuntimeWarning,
                stacklevel=3,
            )


def split_indices(df: pd.DataFrame, mode: str = "temporal", test_size: float = 0.3,
                  seed: int = 42, label_col: str = "label") -> tuple[pd.Index, pd.Index]:
    """返回 (train_index, test_index)。

    temporal: 按时间排序，前 (1-test_size) 训练；时间不可解析时退化为 random 并告警。
    random:   分层随机切分（仅在你确认数据无时间相关性时使用）。
    """
    if not 0.05 <= test_size <= 0.5:
        raise ValueError("test_size 应在 0.05~0.5 之间")
    if len(df) < 20:
        raise ValueError("样本太少（<20 行），无法切分")

    ts = _timestamp_series(df) if mode == "temporal" else None
    if ts is not None and ts.notna().sum() >= len(df) * 0.9:
        order = ts.sort_values(kind="mergesort").index
        cut = int(len(order) * (1 - test_size))
        train, test = pd.Index(order[:cut]), pd.Index(order[cut:])
    else:
        if mode == "temporal":
            warnings.warn("时间戳缺失或不可解析，已退化为随机切分", RuntimeWarning, stacklevel=2)
        from sklearn.model_selection import train_test_split
        stratify = df[label_col] if label_col in df.columns and df[label_col].nunique() > 1 else None
        tr, te = train_test_split(df.index, test_size=test_size, random_state=seed, stratify=stratify)
        train, test = pd.Index(tr), pd.Index(te)

    _coverage_warnings(df, train, test, label_col)
    return train, test
