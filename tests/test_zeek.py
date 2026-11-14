import gzip
from pathlib import Path

import pytest

from flowlab.ingest import read_any
from flowlab.ingest.zeek import ZeekError, read_zeek

CONN = """#separator \\x09
#set_separator\t,
#empty_field\t(empty)
#unset_field\t-
#path\tconn
#open\t2026-11-13-10-00-00
#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p\tproto\tservice\tduration\torig_bytes\tresp_bytes\torig_pkts\tresp_pkts\torig_ip_bytes\tresp_ip_bytes\tconn_state
#types\ttime\tstring\taddr\tport\taddr\tport\tenum\tstring\tinterval\tcount\tcount\tcount\tcount\tcount\tcount\tstring
1700000000.123456\tC1\t10.0.0.1\t51000\t10.0.0.2\t80\ttcp\thttp\t1.500000\t1200\t8000\t8\t10\t1400\t8400\tSF
1700000001.000000\tC2\t10.0.0.3\t52000\t10.0.0.4\t3333\tudp\t-\t0.010000\t900\t0\t30\t0\t960\t0\tS0
1700000002.000000\tC3\t10.0.0.5\t53000\t10.0.0.6\t53\tudp\tdns\t-\t-\t700\t1\t1\t60\t760\tSF
"""


def _write(tmp_path: Path, name="conn.log") -> Path:
    p = tmp_path / name
    p.write_text(CONN, encoding="utf-8")
    return p


def test_read_conn_log(tmp_path):
    df, info = read_zeek(_write(tmp_path))
    assert len(df) == 3
    assert info["format"] == "zeek conn.log"
    assert list(df.columns)[:5] == ["flow_id", "timestamp", "src_ip", "dst_ip", "src_port"]
    row = df.iloc[0]
    assert row["dst_port"] == 80
    assert row["duration_us"] == 1_500_000
    assert row["fwd_bytes"] == 1400 and row["bwd_bytes"] == 8400
    assert row["bytes_per_s"] == pytest.approx((1400 + 8400) / 1.5, rel=1e-3)
    assert row["flow_id"] == "C1"
    assert row["timestamp"] == "2023-11-14 22:13:20.123456"
    assert row["service"] == "http"
    assert row["conn_state"] == "SF"


def test_missing_values_become_zero(tmp_path):
    df, _ = read_zeek(_write(tmp_path))
    row = df.iloc[2]  # duration=-，orig_bytes=-
    assert row["duration_us"] == 0
    assert row["fwd_bytes"] == 60  # 用 orig_ip_bytes（IP 层字节数），不是 orig_bytes
    assert row["bwd_bytes"] == 760


def test_gzip_supported(tmp_path):
    p = tmp_path / "conn.log.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write(CONN)
    df, _ = read_zeek(p)
    assert len(df) == 3


def test_read_any_dispatches_zeek(tmp_path):
    df, info = read_any(_write(tmp_path))
    assert info["format"] == "zeek conn.log"
    assert "duration_us" in df.columns


def test_read_any_detects_renamed_zeek_log(tmp_path):
    df, info = read_any(_write(tmp_path, "traffic.log"))
    assert info["format"] == "zeek conn.log"
    assert len(df) == 3


def test_plain_csv_log_not_misrouted(tmp_path):
    p = tmp_path / "notes.log"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    df, info = read_any(p)
    assert info["format"] != "zeek conn.log"


def test_not_zeek_raises(tmp_path):
    p = tmp_path / "conn.log"
    p.write_text("just some text\nno header here\n", encoding="utf-8")
    with pytest.raises(ZeekError):
        read_zeek(p)
