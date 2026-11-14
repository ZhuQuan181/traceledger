"""把"各种形状的数据"压成一张 flow 表。

研究者的数据长什么样：
- DataFrame / 2D ndarray / list[list]
- dict[str, array]（列式）
- dict 里套 X/y（sklearn 风格）
- list[dict]（记录式）
- npz 里多个数组（X, y / data, labels）
- torch tensor、Series、tuple

目标不是"猜对一切"，而是：能认的认出来，认不出的给出**可执行的错误信息**。
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

LABEL_KEYS = (
    "label",
    "labels",
    "Label",
    "LABEL",
    "y",
    "Y",
    "target",
    "targets",
    "class",
    "classes",
    "attack",
    "is_attack",
    "anomaly",
)
FEATURE_KEYS = ("X", "x", "data", "features", "feature", "df", "frame", "flows", "samples")
# 明显不是流数据的键
META_KEYS = ("meta", "metadata", "info", "config", "params", "scaler", "model", "vocab")


class ShapeError(ValueError):
    """数据形状无法识别。"""


def _arrayify(obj: Any):
    """torch / list / Series → numpy 或保持原样。"""
    if obj is None:
        return None
    # torch tensor：不 import torch，只 duck-type
    if hasattr(obj, "detach") and hasattr(obj, "cpu") and hasattr(obj, "numpy"):
        try:
            return obj.detach().cpu().numpy()
        except Exception:  # noqa: BLE001 - 第三方 tensor 的异常类型不可控
            return obj
    return obj


def _label_from(obj: Any) -> pd.Series | None:
    if obj is None:
        return None
    arr = _arrayify(obj)
    if isinstance(arr, pd.Series):
        return arr.reset_index(drop=True)
    if isinstance(arr, pd.DataFrame):
        return arr.iloc[:, 0].reset_index(drop=True)
    flat = np.asarray(arr).reshape(-1)
    return pd.Series(flat)


def _frame_from_2d(arr: Any, label: Any = None, note: str = "") -> tuple[pd.DataFrame, dict]:
    a = np.asarray(arr)
    if a.ndim == 1:
        a = a.reshape(-1, 1)
    if a.ndim > 2:
        a = a.reshape(a.shape[0], -1)  # 展平：3D 也当特征
        note += f"（原始 {np.asarray(arr).ndim}D 已展平）"
    cols = [f"f_{i}" for i in range(a.shape[1])]
    df = pd.DataFrame(a, columns=cols)
    lab = _label_from(label)
    if lab is not None and len(lab) == len(df):
        df["label"] = lab.to_numpy()
        note += "（标签来自单独的 y）"
    return df, {"shape": f"2D array {a.shape}", "note": note.strip()}


def to_frame(obj: Any, label: Any = None) -> tuple[pd.DataFrame, dict]:
    """任意常见结构 → (DataFrame, 说明)。"""
    obj = _arrayify(obj)

    # 1) DataFrame
    if isinstance(obj, pd.DataFrame):
        df = obj.copy()
        if label is not None and "label" not in df.columns:
            lab = _label_from(label)
            if lab is not None and len(lab) == len(df):
                df["label"] = lab.to_numpy()
        return df.reset_index(drop=True), {"shape": "DataFrame", "note": ""}

    # 2) Series
    if isinstance(obj, pd.Series):
        return obj.to_frame().reset_index(drop=True), {"shape": "Series", "note": ""}

    # 3) ndarray / list[list] / tensor
    if isinstance(obj, np.ndarray) or (
        isinstance(obj, (list, tuple))
        and obj
        and not isinstance(obj[0], (dict, str))
        and not isinstance(obj[0], pd.DataFrame)
    ):
        arr = np.asarray(obj)
        if arr.dtype == object and arr.ndim == 1:
            # 可能是 list[list] 变体
            try:
                arr = np.asarray([np.asarray(x).reshape(-1) for x in obj])
            except Exception:  # noqa: BLE001, S110 - 探测失败后继续走通用分支
                pass
        return _frame_from_2d(arr, label, note="")

    # 4) dict
    if isinstance(obj, dict):
        keys = list(obj.keys())
        lower = {str(k).lower(): k for k in keys}

        # 4a) 明确带特征容器 + 标签
        feat_key = next(
            (
                lower[k]
                for k in FEATURE_KEYS
                if k in lower and not isinstance(obj[lower[k]], (str, bytes))
            ),
            None,
        )
        lab_key = next((lower[k] for k in LABEL_KEYS if k in lower), None)
        if feat_key is not None:
            df, info = to_frame(obj[feat_key], label=obj.get(lab_key) if lab_key else label)
            used = [str(feat_key)] + ([str(lab_key)] if lab_key else [])
            info["note"] = f"从字典取 {'/'.join(used)}；{info['note']}".strip("；")
            return df, info

        # 4b) 列式：所有值都是等长序列
        seq_items = {
            k: v
            for k, v in obj.items()
            if str(k).lower() not in META_KEYS
            and isinstance(_arrayify(v), (list, tuple, np.ndarray, pd.Series))
        }
        if len(seq_items) >= 2 and len(seq_items) >= len(obj) * 0.6:
            lengths = {len(np.asarray(_arrayify(v)).reshape(-1)) for v in seq_items.values()}
            if len(lengths) == 1:
                df = pd.DataFrame(
                    {str(k): np.asarray(_arrayify(v)).reshape(-1) for k, v in seq_items.items()}
                )
                lab = _label_from(label)
                if lab is not None and len(lab) == len(df):
                    df["label"] = lab.to_numpy()
                return df, {"shape": f"列式字典（{len(seq_items)} 列）", "note": "每个键当作一列"}

        raise ShapeError(
            "字典结构无法识别。已看到键: "
            + ", ".join(map(str, keys[:12]))
            + "。支持：{列名: 数组}、{X: 矩阵, y: 标签}、{data: ..., labels: ...}"
        )

    # 5) list[dict]
    if isinstance(obj, (list, tuple)) and obj and isinstance(obj[0], dict):
        return pd.DataFrame(obj).reset_index(drop=True), {
            "shape": "记录列表",
            "note": "每个 dict 一行",
        }

    # 6) list of DataFrame → 拼接
    if isinstance(obj, (list, tuple)) and obj and isinstance(obj[0], pd.DataFrame):
        return pd.concat(obj, ignore_index=True), {
            "shape": f"{len(obj)} 个 DataFrame 拼接",
            "note": "",
        }

    raise ShapeError(
        f"不支持的数据类型: {type(obj).__name__}。"
        "支持 DataFrame / ndarray / list / dict / Series / torch tensor。"
    )


def describe_object(obj: Any) -> str:
    """给错误信息用的一句话描述。"""
    t = type(obj).__name__
    if isinstance(obj, dict):
        return f"dict(keys={list(map(str, obj.keys()))[:10]})"
    if isinstance(obj, np.ndarray):
        return f"ndarray(shape={obj.shape}, dtype={obj.dtype})"
    if isinstance(obj, (list, tuple)):
        inner = type(obj[0]).__name__ if obj else "empty"
        return f"{t}(len={len(obj)}, first={inner})"
    return t
