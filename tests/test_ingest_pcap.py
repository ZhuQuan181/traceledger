import pandas as pd
import pytest

from flowlab.ingest import pcap

TSHARK_OUT = "\n".join(
    [
        "1700000000.000000\t10.0.0.1\t10.0.0.2\t1234\t80\t\t\t100\t6",
        "1700000001.000000\t10.0.0.1\t10.0.0.2\t1234\t80\t\t\t200\t6",
        "1700000500.000000\t10.0.0.1\t10.0.0.2\t1234\t80\t\t\t300\t6",
        "1700000000.500000\t10.0.0.3\t10.0.0.4\t\t53\t5555\t53\t90\t17",
    ]
)


def test_parse_tshark_output():
    pkts = pcap.parse_tshark_output(TSHARK_OUT)
    assert len(pkts) == 4
    assert pkts.iloc[0]["dst_port"] == 80
    assert pkts.iloc[3]["protocol"] == 17
    assert pkts.iloc[3]["src_port"] == 5555


def test_flows_split_on_timeout():
    pkts = pcap.parse_tshark_output(TSHARK_OUT)
    flows = pcap.flows_from_packets(pkts, flow_timeout=120)
    # 前两条同流；第三条隔了 499s -> 新流；UDP 一条单独成流
    assert len(flows) == 3
    f = flows.sort_values("Total Fwd Packets", ascending=False).iloc[0]
    assert f["Total Fwd Packets"] == 2
    assert f["Total Length of Fwd Packets"] == 300
    assert f["Flow Duration"] == 1_000_000


def test_reverse_packets_join_the_same_bidirectional_flow():
    packets = pd.DataFrame(
        [
            {
                "ts": 1.0,
                "src_ip": "10.0.0.1",
                "dst_ip": "10.0.0.2",
                "src_port": 50000,
                "dst_port": 443,
                "bytes": 100,
                "protocol": 6,
            },
            {
                "ts": 1.2,
                "src_ip": "10.0.0.2",
                "dst_ip": "10.0.0.1",
                "src_port": 443,
                "dst_port": 50000,
                "bytes": 300,
                "protocol": 6,
            },
            {
                "ts": 1.5,
                "src_ip": "10.0.0.1",
                "dst_ip": "10.0.0.2",
                "src_port": 50000,
                "dst_port": 443,
                "bytes": 50,
                "protocol": 6,
            },
        ]
    )
    flows = pcap.flows_from_packets(packets)
    assert len(flows) == 1
    row = flows.iloc[0]
    assert row["Source IP"] == "10.0.0.1"
    assert row["Total Fwd Packets"] == 2
    assert row["Total Backward Packets"] == 1
    assert row["Total Length of Fwd Packets"] == 150
    assert row["Total Length of Bwd Packets"] == 300


def test_missing_tshark_message(tmp_path, monkeypatch):
    monkeypatch.setattr(pcap.shutil, "which", lambda _: None)
    existing = tmp_path / "empty.pcap"
    existing.write_bytes(b"")
    with pytest.raises(pcap.PcapUnavailable, match="tshark"):
        pcap.read_pcap(existing)


def test_read_pcap_real_file(tmp_path):
    """端到端：真实 pcap（自建，无 scapy 依赖）→ 标准化列名。"""
    import subprocess
    import sys

    out = tmp_path / "t.pcap"
    r = subprocess.run(
        [sys.executable, "scripts/make_test_pcap.py", str(out)], capture_output=True, text=True
    )
    if r.returncode != 0:
        pytest.skip(f"生成 pcap 失败: {r.stderr[:200]}")
    if not pcap.tshark_available():
        pytest.skip("未安装 tshark")
    df = pcap.read_pcap(out, flow_timeout=120)
    assert len(df) == 3
    assert {"src_ip", "dst_ip", "dst_port", "bytes_per_s"} <= set(df.columns)
    assert 1 <= df["fwd_packets"].max() <= 8
