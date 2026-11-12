"""CSV 读取：自动识别分隔符与编码。"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import pandas as pd

from flowlab.schema import normalize_columns

_ENCODINGS = ("utf-8-sig", "utf-8", "gbk", "latin-1")


def sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def read_csv(path: str | Path) -> pd.DataFrame:
    """读取 CSV，返回列名标准化后的 DataFrame。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")
    raw = p.read_bytes()
    sample = raw[:65536].decode("utf-8", errors="ignore")
    sep = sniff_delimiter(sample)

    last_err: Exception | None = None
    for enc in _ENCODINGS:
        try:
            df = pd.read_csv(io.BytesIO(raw), sep=sep, encoding=enc,
                             skipinitialspace=True, low_memory=False)
            if df.shape[1] >= 2:
                return normalize_columns(df)
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:  # pragma: no cover
            last_err = exc
    raise ValueError(f"无法解析 CSV: {p} ({last_err})")
