"""表格类格式读取：json / jsonl / parquet / npy / npz / pickle / excel。

所有分支最终都走 `adapters.to_frame()`，所以形状识别逻辑只有一份。
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from flowlab.adapters import ShapeError, describe_object, to_frame
from flowlab.ingest.csv import read_csv

PICKLE_SUFFIXES = {".pkl", ".pickle", ".p"}

EXTRA_HINT = {
    ".parquet": "需要 pyarrow：安装 data 扩展（uv sync --extra data）",
    ".xlsx": "需要 openpyxl：安装 data 扩展（uv sync --extra data）",
    ".xls": "需要 xlrd：安装 data 扩展（uv sync --extra data）",
}


def _deps(fn, suffix: str):
    try:
        return fn()
    except ImportError as exc:
        raise ShapeError(f"读取 {suffix} 失败：{EXTRA_HINT.get(suffix, str(exc))}") from exc


def read_table(path: str | Path, allow_pickle: bool = False) -> tuple[pd.DataFrame, dict]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")
    suffix = p.suffix.lower()

    if suffix in PICKLE_SUFFIXES:
        if not allow_pickle:
            raise ShapeError(
                "pickle 会在加载时执行任意代码，默认禁用。确认文件可信后加 --allow-pickle，"
                "或在网页上勾选「允许 pickle」。"
            )
        with p.open("rb") as f:
            obj = pickle.load(f)  # noqa: S301 - 已显式确认
        try:
            df, info = to_frame(obj)
        except ShapeError as exc:
            raise ShapeError(f"{exc}（pickle 里是 {describe_object(obj)}）") from exc
        info["format"] = "pickle"
        info["pickle_object"] = describe_object(obj)
        return df, info

    if suffix == ".npy":
        arr = np.load(p, allow_pickle=False)
        df, info = to_frame(arr)
        info["format"] = "npy"
        return df, info

    if suffix == ".npz":
        with np.load(p, allow_pickle=False) as npz:
            obj = {k: npz[k] for k in npz.files}
        df, info = to_frame(obj)
        info["format"] = "npz"
        return df, info

    if suffix == ".parquet":
        df = _deps(lambda: pd.read_parquet(p), suffix)
        return df.reset_index(drop=True), {"format": "parquet", "shape": "DataFrame", "note": ""}

    if suffix in {".jsonl", ".ndjson", ".jl"}:
        df = pd.read_json(p, lines=True)
        out, info = to_frame(df)
        info["format"] = "jsonl"
        return out, info

    if suffix == ".json":
        with p.open(encoding="utf-8") as f:
            obj = json.load(f)
        try:
            df, info = to_frame(obj)
        except ShapeError as exc:
            raise ShapeError(f"{exc}（JSON 顶层是 {describe_object(obj)}）") from exc
        info["format"] = "json"
        return df, info

    if suffix in {".xlsx", ".xls"}:
        df = _deps(lambda: pd.read_excel(p), suffix)
        return df.reset_index(drop=True), {"format": "excel", "shape": "DataFrame", "note": ""}

    # 默认当分隔符文本
    df = read_csv(p)
    return df, {"format": suffix.lstrip(".") or "csv", "shape": "DataFrame", "note": ""}
