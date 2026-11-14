"""特征工程：把原始计数变成可比、可解释的速率特征。

背景：CICFlowMeter 对单包流的 duration 记为 0（或极小的微秒数），
直接相除会得到 1e8 级别的 bytes/s。不同抓包批次里这种失真程度不同，
导致"速率"这一类特征跨数据集根本不可比。

处理方式：
1. 速率统一用 `duration_ms` 兜底（最小 1 ms），并保留原始值供审计；
2. 增加 `bytes_per_pkt`、`is_single_packet`，让模型能用上绝对量；
3. 不做静默截断 —— 变换写进报告，谁都能复算。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MIN_DURATION_MS = 1.0

PAIRS = (
    ("fwd_packets", "bwd_packets", "packets"),
    ("fwd_bytes", "bwd_bytes", "bytes"),
)


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def add_engineered_features(
    df: pd.DataFrame, min_duration_ms: float = MIN_DURATION_MS
) -> pd.DataFrame:
    """返回新 DataFrame（不改原对象），补上稳健速率与派生特征。"""
    out = df.copy()

    # 保留原始速率，便于对照"修正前后差多少"
    if "bytes_per_s" in out.columns:
        out["raw_bytes_per_s"] = _num(out, "bytes_per_s")
    if "packets_per_s" in out.columns:
        out["raw_packets_per_s"] = _num(out, "packets_per_s")

    has_duration = "duration_us" in out.columns or "duration_ms" in out.columns
    if has_duration:
        if "duration_us" in out.columns:
            dur_ms = _num(out, "duration_us") / 1000.0
        else:
            dur_ms = _num(out, "duration_ms")
        dur_ms_eff = np.maximum(dur_ms, min_duration_ms)
        out["duration_ms"] = dur_ms.round(3)
        out["duration_ms_effective"] = np.round(dur_ms_eff, 3)

    # 只有计数组成列存在时才重算速率。若数据本身已经提供 bytes_per_s /
    # packets_per_s 而没有组成列，直接保留原值，绝不能静默改成 0。
    has_packets = "fwd_packets" in out.columns or "bwd_packets" in out.columns
    has_bytes = "fwd_bytes" in out.columns or "bwd_bytes" in out.columns
    if has_packets and has_duration:
        packets = _num(out, "fwd_packets") + _num(out, "bwd_packets")
        out["packets_per_s"] = (packets / (dur_ms_eff / 1000.0)).round(3)
    if has_bytes and has_duration:
        nbytes = _num(out, "fwd_bytes") + _num(out, "bwd_bytes")
        out["bytes_per_s"] = (nbytes / (dur_ms_eff / 1000.0)).round(3)
    if has_packets and has_bytes:
        packets = _num(out, "fwd_packets") + _num(out, "bwd_packets")
        nbytes = _num(out, "fwd_bytes") + _num(out, "bwd_bytes")
        out["bytes_per_pkt"] = (nbytes / np.maximum(packets, 1.0)).round(3)
        out["is_single_packet"] = (packets <= 1).astype(int)
    elif "bytes_per_s" in out.columns and "packets_per_s" in out.columns:
        # 没有绝对计数时，两条速率共用同一时长，比值仍可安全还原每个包的平均字节数。
        pps = _num(out, "packets_per_s").replace(0.0, np.nan)
        out["bytes_per_pkt"] = (_num(out, "bytes_per_s") / pps).round(3)
    return out


def describe(min_duration_ms: float = MIN_DURATION_MS) -> dict:
    return {
        "min_duration_ms": min_duration_ms,
        "derived": [
            "duration_ms",
            "duration_ms_effective",
            "bytes_per_s",
            "packets_per_s",
            "bytes_per_pkt",
            "is_single_packet",
        ],
        "note": "单包流速率以 1ms 兜底计算，同时用 bytes_per_pkt 保留绝对量。",
    }
