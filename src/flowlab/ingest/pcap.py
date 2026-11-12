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
    return pd.DataFrame(rows, columns=["ts", "src_ip", "dst_ip", "src_port", "dst_port", "bytes", "protocol"])


def flows_from_packets(pkts: pd.DataFrame, flow_timeout: float = 120.0) -> pd.DataFrame:
    """按五元组 + 空闲超时聚合成流，输出与 CSV 路径相同的列名。"""
    cols = ["Flow ID", "Source IP", "Destination IP", "Source Port", "Destination Port",
            "Protocol", "Timestamp", "Flow Duration", "Total Fwd Packets",
            "Total Backward Packets", "Total Length of Fwd Packets",
            "Total Length of Bwd Packets", "Flow Bytes/s", "Flow Packets/s"]
    if pkts.empty:
        return pd.DataFrame(columns=cols)

    pkts = pkts.sort_values("ts", kind="mergesort")
    rows: list[dict] = []
    for (src, dst, sport, dport, proto), g in pkts.groupby(
        ["src_ip", "dst_ip", "src_port", "dst_port", "protocol"], sort=False
    ):
        start = last = None
        npkts = nbytes = 0
        for ts, b in zip(g["ts"].to_numpy(), g["bytes"].to_numpy()):
            if start is None or ts - last > flow_timeout:
                if start is not None:
                    rows.append(_row(src, dst, sport, dport, proto, start, last, npkts, nbytes))
                start, npkts, nbytes = ts, 0, 0
            last = ts
            npkts += 1
            nbytes += int(b)
        rows.append(_row(src, dst, sport, dport, proto, start, last, npkts, nbytes))

    rows.sort(key=lambda r: r["Timestamp"])
    for i, r in enumerate(rows):
        r["Flow ID"] = (f"{r['Source IP']}-{r['Destination IP']}-{r['Destination Port']}"
                        f"-{r['Protocol']}-{i}")
    return pd.DataFrame(rows, columns=cols)


def _row(src, dst, sport, dport, proto, start, last, npkts, nbytes) -> dict:
    dur_us = max(int((last - start) * 1e6), 1)
    dur_s = dur_us / 1e6
    return {
        "Source IP": src,
        "Destination IP": dst,
        "Source Port": int(sport),
        "Destination Port": int(dport),
        "Protocol": int(proto),
        "Timestamp": pd.to_datetime(start, unit="s").strftime("%Y-%m-%d %H:%M:%S"),
        "Flow Duration": dur_us,
        "Total Fwd Packets": npkts,
        "Total Backward Packets": 0,
        "Total Length of Fwd Packets": nbytes,
        "Total Length of Bwd Packets": 0,
        "Flow Bytes/s": nbytes / dur_s,
        "Flow Packets/s": npkts / dur_s,
    }


def read_pcap(path: str | Path, flow_timeout: float = 120.0) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")
    return flows_from_packets(parse_tshark_output(_run_tshark(p)), flow_timeout=flow_timeout)
