"""pcap 读取：调 tshark 导出字段，再在 Python 侧重组成流。

设计取舍：
- 只做**离线**解析，不追求线速；大文件请先用 editcap 切片。
- tshark 不在时抛 PcapUnavailable，并给出安装提示（不自动装软件）。
- 无标签 —— pcap 通常没有 ground truth，因此走 score/解释路径而不是评估路径。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pandas as pd

FIELDS = [
    "frame.time_epoch",
    "ip.src",
    "ip.dst",
    "tcp.srcport",
    "tcp.dstport",
    "udp.srcport",
    "udp.dstport",
    "frame.len",
    "ip.proto",
]


class PcapUnavailable(RuntimeError):
    """tshark 未安装或不可执行。"""


def tshark_available() -> bool:
    return shutil.which("tshark") is not None


def _run_tshark(path: Path) -> str:
    if not tshark_available():
        raise PcapUnavailable(
            "未找到 tshark。安装方式：Ubuntu `sudo apt install tshark`，"
            "macOS `brew install --cask wireshark`，Windows 装 Wireshark 时勾选 TShark。"
        )
    cmd = ["tshark", "-r", str(path), "-T", "fields", "-E", "separator=\t", "-E", "occurrence=f"]
    for f in FIELDS:
        cmd += ["-e", f]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"tshark 解析失败: {proc.stderr.strip()[:300]}")
    return proc.stdout


def parse_tshark_output(text: str) -> pd.DataFrame:
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < len(FIELDS):
            parts += [""] * (len(FIELDS) - len(parts))
        ts, src, dst, tsport, tdport, usport, udport, length, proto = parts[: len(FIELDS)]
        sport = tsport or usport
        dport = tdport or udport
        if not src or not dst:
            continue
        try:
            rows.append(
                {
                    "ts": float(ts) if ts else 0.0,
                    "src_ip": src,
                    "dst_ip": dst,
                    "src_port": int(sport) if sport else 0,
                    "dst_port": int(dport) if dport else 0,
                    "bytes": int(length) if length else 0,
                    "protocol": int(proto) if str(proto).isdigit() else 6,
                }
            )
        except ValueError:
            continue
    return pd.DataFrame(
        rows, columns=["ts", "src_ip", "dst_ip", "src_port", "dst_port", "bytes", "protocol"]
    )


def flows_from_packets(pkts: pd.DataFrame, flow_timeout: float = 120.0) -> pd.DataFrame:
    """按双向五元组 + 空闲超时聚合成流，输出与 CSV 路径相同的列名。

    首包方向定义为源到目的方向；反向包计入 bwd_*。若只用原始五元组分组，
    TCP 回包会变成另一条流，backward 特征将永久为 0。
    """
    cols = [
        "Flow ID",
        "Source IP",
        "Destination IP",
        "Source Port",
        "Destination Port",
        "Protocol",
        "Timestamp",
        "Flow Duration",
        "Total Fwd Packets",
        "Total Backward Packets",
        "Total Length of Fwd Packets",
        "Total Length of Bwd Packets",
        "Flow Bytes/s",
        "Flow Packets/s",
    ]
    if pkts.empty:
        return pd.DataFrame(columns=cols)

    pkts = pkts.sort_values("ts", kind="mergesort")
    active: dict[tuple, dict] = {}
    rows: list[dict] = []

    def _finish(state: dict) -> None:
        src, sport = state["src_ep"]
        dst, dport = state["dst_ep"]
        rows.append(
            _row(
                src,
                dst,
                sport,
                dport,
                state["protocol"],
                state["start"],
                state["last"],
                state["fwd_packets"],
                state["bwd_packets"],
                state["fwd_bytes"],
                state["bwd_bytes"],
            )
        )

    for packet in pkts.itertuples(index=False):
        start_ep = (str(packet.src_ip), int(packet.src_port))
        end_ep = (str(packet.dst_ip), int(packet.dst_port))
        protocol = int(packet.protocol)
        endpoints = tuple(sorted((start_ep, end_ep)))
        key = (*endpoints, protocol)
        ts = float(packet.ts)
        state = active.get(key)
        if state is not None and ts - state["last"] > flow_timeout:
            _finish(state)
            state = None
        if state is None:
            state = {
                "src_ep": start_ep,
                "dst_ep": end_ep,
                "protocol": protocol,
                "start": ts,
                "last": ts,
                "fwd_packets": 0,
                "bwd_packets": 0,
                "fwd_bytes": 0,
                "bwd_bytes": 0,
            }
            active[key] = state
        forward = start_ep == state["src_ep"]
        if forward:
            state["fwd_packets"] += 1
            state["fwd_bytes"] += int(packet.bytes)
        else:
            state["bwd_packets"] += 1
            state["bwd_bytes"] += int(packet.bytes)
        state["last"] = ts

    for state in active.values():
        _finish(state)

    rows.sort(key=lambda r: r["Timestamp"])
    for i, r in enumerate(rows):
        r["Flow ID"] = (
            f"{r['Source IP']}-{r['Destination IP']}-{r['Destination Port']}-{r['Protocol']}-{i}"
        )
    return pd.DataFrame(rows, columns=cols)


def _row(
    src, dst, sport, dport, proto, start, last, fwd_packets, bwd_packets, fwd_bytes, bwd_bytes
) -> dict:
    dur_us = max(int((last - start) * 1e6), 1)
    dur_s = dur_us / 1e6
    packets = fwd_packets + bwd_packets
    nbytes = fwd_bytes + bwd_bytes
    timestamp = pd.to_datetime(start, unit="s").strftime("%Y-%m-%d %H:%M:%S.%f")
    timestamp = timestamp.rstrip("0").rstrip(".")
    return {
        "Source IP": src,
        "Destination IP": dst,
        "Source Port": int(sport),
        "Destination Port": int(dport),
        "Protocol": int(proto),
        "Timestamp": timestamp,
        "Flow Duration": dur_us,
        "Total Fwd Packets": fwd_packets,
        "Total Backward Packets": bwd_packets,
        "Total Length of Fwd Packets": fwd_bytes,
        "Total Length of Bwd Packets": bwd_bytes,
        "Flow Bytes/s": nbytes / dur_s,
        "Flow Packets/s": packets / dur_s,
    }


def read_pcap(path: str | Path, flow_timeout: float = 120.0) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")
    from flowlab.schema import normalize_columns

    return normalize_columns(
        flows_from_packets(parse_tshark_output(_run_tshark(p)), flow_timeout=flow_timeout)
    )
