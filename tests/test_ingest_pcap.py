import pandas as pd
import pytest

from flowlab.ingest import pcap


TSHARK_OUT = "\n".join([
    "1700000000.000000\t10.0.0.1\t10.0.0.2\t1234\t80\t\t\t100\t6",
    "1700000001.000000\t10.0.0.1\t10.0.0.2\t1234\t80\t\t\t200\t6",
    "1700000500.000000\t10.0.0.1\t10.0.0.2\t1234\t80\t\t\t300\t6",
    "1700000000.500000\t10.0.0.3\t10.0.0.4\t\t53\t5555\t53\t90\t17",
])


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


def test_missing_tshark_message():
    if pcap.tshark_available():
        pytest.skip("本机已装 tshark")
    with pytest.raises(pcap.PcapUnavailable):
        pcap.read_pcap("nope.pcap")


def test_read_pcap_real_file(tmp_path):
    """端到端：真实 pcap（自建，无 scapy 依赖）→ 标准化列名。"""
    import subprocess, sys
    out = tmp_path / "t.pcap"
    r = subprocess.run([sys.executable, "scripts/make_test_pcap.py", str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip(f"生成 pcap 失败: {r.stderr[:200]}")
    if not pcap.tshark_available():
        pytest.skip("未安装 tshark")
    df = pcap.read_pcap(out, flow_timeout=120)
    assert len(df) == 3
    assert {"src_ip", "dst_ip", "dst_port", "bytes_per_s"} <= set(df.columns)
    assert df["fwd_packets"].max() == 3
