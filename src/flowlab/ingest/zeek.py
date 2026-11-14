"""Zeek conn.log 读取：干掉"先跑 CICFlowMeter"这一步。

Zeek 的 conn.log 本身就是流级别的（每条记录=一条连接），所以不需要再聚合；
只要按 `#fields` 表头把列名映射到我们的 schema。

支持：
- 纯文本 conn.log / conn.log.gz
- 自定义 `#separator`（默认 \x09）
- 缺失值 `-`、`(empty)` → NaN
"""

from __future__ import annotations

import csv
import gzip
from pathlib import Path

import pandas as pd

SEP_DEFAULT = "\x09"

# Zeek 字段 -> 内部标准列
FIELD_MAP = {
    "ts": "timestamp",
    "id.orig_h": "src_ip",
    "id.resp_h": "dst_ip",
    "id.orig_p": "src_port",
    "id.resp_p": "dst_port",
    "proto": "protocol",
    "duration": None,  # 秒 -> 微秒，单独处理
    "orig_pkts": "fwd_packets",
    "resp_pkts": "bwd_packets",
    "orig_ip_bytes": "fwd_bytes",
    "resp_ip_bytes": "bwd_bytes",
}

MISSING = {"-", "(empty)", "", "nan"}


class ZeekError(ValueError):
    """不是可解析的 Zeek 日志。"""


def _open(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def parse_header(lines: list[str]) -> tuple[dict, list[str]]:
    """返回 (#separator 设置, 字段列表)。"""
    sep = SEP_DEFAULT
    fields: list[str] = []
    for line in lines:
        if not line.startswith("#"):
            break
        if line.startswith("#separator"):
            raw = line.split(" ", 1)[1].strip() if " " in line else SEP_DEFAULT
            sep = codecs_unescape(raw)
        elif line.startswith("#fields"):
            fields = line.split(sep)[1:]
    if not fields:
        raise ZeekError("找不到 #fields 表头，这不像是 Zeek 的 conn.log")
    return {"separator": sep}, fields


def codecs_unescape(raw: str) -> str:
    """Zeek 把分隔符写成 \\x09 这样的转义。"""
    raw = raw.strip()
    if raw.startswith("\\x") or raw.startswith("\\X"):
        try:
            return chr(int(raw[2:], 16))
        except ValueError:
            return "\t"
    if raw == "\\t":
        return "\t"
    return raw


def read_zeek(path: str | Path) -> tuple[pd.DataFrame, dict]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")

    header_lines: list[str] = []
    with _open(p) as f:
        for line in f:
            if line.startswith("#"):
                header_lines.append(line.rstrip("\n"))
            else:
                first_data = line
                break
        else:
            first_data = ""

    meta, fields = parse_header(header_lines)
    sep = meta["separator"]
    if sep == "\t" and "\t" not in first_data and "," in first_data:
        sep = ","

    rows = []
    with _open(p) as f:
        reader = csv.reader((line for line in f if not line.startswith("#")), delimiter=sep)
        for rec in reader:
            if not rec or len(rec) < 2:
                continue
            rec = (rec + [""] * len(fields))[: len(fields)]
            row = dict(zip(fields, rec))
            if row.get("ts") in MISSING:
                continue
            rows.append(row)

    if not rows:
        raise ZeekError("conn.log 里没有数据行")

    raw = pd.DataFrame(rows)
    out = pd.DataFrame(index=raw.index)

    def num(col: str) -> pd.Series:
        if col not in raw.columns:
            return pd.Series([float("nan")] * len(raw), index=raw.index)
        s = raw[col].replace(list(MISSING), "nan")
        return pd.to_numeric(s, errors="coerce")

    timestamps = pd.to_datetime(num("ts"), unit="s", errors="coerce")
    out["timestamp"] = (
        timestamps.dt.strftime("%Y-%m-%d %H:%M:%S.%f").str.rstrip("0").str.rstrip(".")
    )
    for src, dst in (("id.orig_h", "src_ip"), ("id.resp_h", "dst_ip")):
        out[dst] = raw[src].replace(list(MISSING), "") if src in raw.columns else ""
    for src, dst in (("id.orig_p", "src_port"), ("id.resp_p", "dst_port")):
        s = (
            raw[src].replace(list(MISSING), "nan")
            if src in raw.columns
            else pd.Series(["nan"] * len(raw))
        )
        out[dst] = pd.to_numeric(s, errors="coerce").fillna(0).astype("int64")
    out["protocol"] = raw["proto"].replace(list(MISSING), "") if "proto" in raw.columns else ""
    out["duration_us"] = (num("duration").fillna(0) * 1e6).round().astype("int64")
    out["fwd_packets"] = num("orig_pkts").fillna(0).astype("int64")
    out["bwd_packets"] = num("resp_pkts").fillna(0).astype("int64")
    out["fwd_bytes"] = num("orig_ip_bytes").fillna(0).astype("int64")
    out["bwd_bytes"] = num("resp_ip_bytes").fillna(0).astype("int64")

    dur_s = (out["duration_us"] / 1e6).clip(lower=0.001)
    out["bytes_per_s"] = ((out["fwd_bytes"] + out["bwd_bytes"]) / dur_s).round(3)
    out["packets_per_s"] = ((out["fwd_packets"] + out["bwd_packets"]) / dur_s).round(3)
    if "uid" in raw.columns:
        out.insert(0, "flow_id", raw["uid"].replace(list(MISSING), "").astype(str))
    else:
        out.insert(0, "flow_id", [f"zeek-{i}" for i in range(len(out))])
    if "service" in raw.columns:
        out["service"] = raw["service"].replace(list(MISSING), "").astype(str)
    if "conn_state" in raw.columns:
        out["conn_state"] = raw["conn_state"].replace(list(MISSING), "").astype(str)

    info = {
        "format": "zeek conn.log",
        "shape": f"{len(out)} 条连接",
        "note": f"字段映射自 {len(fields)} 个 Zeek 字段，保留 uid / conn_state / service",
    }
    return out, info


def looks_like_zeek(path: Path) -> bool:
    """只认真正的 Zeek 日志：文件名像 conn，或文件头有 #separator/#fields。"""
    name = path.name.lower()
    if "conn" in name and name.endswith((".log", ".log.gz")):
        return True
    if not name.endswith((".log", ".log.gz")):
        return False
    try:
        with _open(path) as f:
            # Zeek 的标准头里 #fields 通常在第六行之后；多扫一些，
            # 这样用户把 conn.log 改成 traffic.log 时也不会误判成 CSV。
            for _ in range(200):
                line = f.readline()
                if line.startswith("#separator") or line.startswith("#fields"):
                    return True
                if not line:
                    break
    except (OSError, UnicodeDecodeError):
        return False
    return False
