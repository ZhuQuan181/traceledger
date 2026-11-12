"""统一 schema：把 CICFlowMeter / Zeek / 自建 CSV 的列名映射到内部标准名。"""
from __future__ import annotations

import re

import pandas as pd

# CICFlowMeter 常见列名 -> 内部标准名
CANON: dict[str, str] = {
    "flow_id": "flow_id",
    "source_ip": "src_ip",
    "src_ip": "src_ip",
    "destination_ip": "dst_ip",
    "dst_ip": "dst_ip",
    "source_port": "src_port",
    "src_port": "src_port",
    "destination_port": "dst_port",
    "dst_port": "dst_port",
    "protocol": "protocol",
    "timestamp": "timestamp",
    "flow_duration": "duration_us",
    "total_fwd_packets": "fwd_packets",
    "total_backward_packets": "bwd_packets",
    "total_length_of_fwd_packets": "fwd_bytes",
    "total_length_of_bwd_packets": "bwd_bytes",
    "flow_bytes_s": "bytes_per_s",
    "flow_packets_s": "packets_per_s",
    "label": "label",
}

# 不参与训练、但保留用于切分/审计的列
META_COLUMNS = {"flow_id", "src_ip", "dst_ip", "src_port", "timestamp", "label"}


def normalize_name(name: str) -> str:
    """小写、去空白、连字符/点转下划线、压缩重复下划线。"""
    s = str(name).strip().lower()
    s = re.sub(r"[\s\-\.]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """返回列名已标准化的副本；未识别的列保留原名（但已规范化）。"""
    mapping = {}
    for col in df.columns:
        norm = normalize_name(col)
        mapping[col] = CANON.get(norm, norm)
    out = df.rename(columns=mapping)
    # 去掉因映射产生的重复列（保留第一个）
    return out.loc[:, ~out.columns.duplicated()]
