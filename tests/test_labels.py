import pandas as pd
import pytest

from flowlab.labels import attach_labels, guess_sidecar


def _flows():
    return pd.DataFrame({
        "flow_id": ["a", "b", "c"],
        "src_ip": ["10.0.0.1", "10.0.0.1", "10.0.0.9"],
        "dst_ip": ["10.0.0.2", "10.0.0.2", "10.0.0.8"],
        "src_port": [1000, 1000, 2000],
        "dst_port": [80, 80, 53],
        "protocol": [6, 6, 17],
    })


def test_by_flow_id(tmp_path):
    p = tmp_path / "lab.csv"
    pd.DataFrame({"flow_id": ["a", "b", "c"], "label": ["BENIGN", "DDoS", "BENIGN"]}).to_csv(p, index=False)
    out, info = attach_labels(_flows(), p)
    assert info["mode"] == "flow_id"
    assert list(out["label"]) == ["BENIGN", "DDoS", "BENIGN"]


def test_by_5tuple_any_attack_wins(tmp_path):
    p = tmp_path / "lab.csv"
    # 同一五元组有两条：一条 BENIGN、一条 DDoS -> 合并后应视为攻击
    pd.DataFrame({
        "src_ip": ["10.0.0.1", "10.0.0.1"],
        "dst_ip": ["10.0.0.2", "10.0.0.2"],
        "src_port": [1000, 1000],
        "dst_port": [80, 80],
        "protocol": [6, 6],
        "label": ["BENIGN", "DDoS"],
    }).to_csv(p, index=False)
    out, info = attach_labels(_flows(), p)
    assert info["mode"].startswith("src_ip")
    assert set(out.loc[out["dst_port"] == 80, "label"]) == {"DDoS"}


def test_by_row_order(tmp_path):
    p = tmp_path / "lab.csv"
    pd.DataFrame({"label": ["BENIGN", "BENIGN", "DDoS"]}).to_csv(p, index=False)
    out, info = attach_labels(_flows(), p)
    assert info["mode"] == "row_order"
    assert out.iloc[2]["label"] == "DDoS"


def test_mismatch_raises(tmp_path):
    p = tmp_path / "lab.csv"
    pd.DataFrame({"label": ["BENIGN"]}).to_csv(p, index=False)
    with pytest.raises(ValueError):
        attach_labels(_flows().drop(columns=["flow_id", "src_ip", "dst_ip", "src_port", "protocol"]), p)


def test_sidecar_guess(tmp_path):
    target = tmp_path / "cap.pcap"
    target.write_bytes(b"x")
    assert guess_sidecar(target) is None
    (tmp_path / "cap.pcap.labels.csv").write_text("label\nBENIGN\n")
    assert guess_sidecar(target).name == "cap.pcap.labels.csv"
