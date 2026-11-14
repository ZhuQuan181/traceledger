"""按后缀分发到具体读取器。"""

from __future__ import annotations

from pathlib import Path

from flowlab.adapters import ShapeError
from flowlab.ingest.csv import read_csv
from flowlab.ingest.table import read_table

PCAP_SUFFIXES = {".pcap", ".pcapng"}


def read_any(path: str | Path, allow_pickle: bool = False) -> tuple[object, dict]:
    """返回 (DataFrame, 读取说明)。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")
    if p.suffix.lower() in PCAP_SUFFIXES:
        from flowlab.ingest.pcap import read_pcap

        return read_pcap(p), {
            "format": "pcap",
            "shape": "flows",
            "note": "tshark 解析后按五元组聚合",
        }
    from flowlab.ingest.zeek import looks_like_zeek, read_zeek

    if looks_like_zeek(p):
        return read_zeek(p)
    try:
        return read_table(p, allow_pickle=allow_pickle)
    except ShapeError:
        raise
    except Exception as exc:  # 未知解析错误统一成可读信息
        raise ShapeError(f"解析 {p.name} 失败: {exc}") from exc


def supported_formats() -> list[str]:
    return [
        "csv",
        "tsv",
        "pcap",
        "pcapng",
        "zeek conn.log",
        "json",
        "jsonl",
        "parquet",
        "npy",
        "npz",
        "pkl",
        "pickle",
        "xlsx",
        "xls",
    ]


__all__ = ["read_any", "read_csv", "read_table", "supported_formats"]
