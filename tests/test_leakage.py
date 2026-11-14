import pandas as pd

from flowlab.features.leakage import detect
from flowlab.schema import normalize_columns
from flowlab.synthetic import generate


def _df(leakage_only: bool = False):
    return normalize_columns(
        generate(n_normal=500, n_attack=100, seed=11, leakage_only=leakage_only)
    )


def test_id_leak_on_flow_id():
    warns = detect(_df(), split="temporal")
    rules = {w["rule"]: w for w in warns}
    assert "id_leak" in rules
    assert "flow_id" in rules["id_leak"]["columns"]


def test_time_leak_only_with_random_split():
    assert any(w["rule"] == "time_leak" for w in detect(_df(), split="random"))
    assert not any(w["rule"] == "time_leak" for w in detect(_df(), split="temporal"))


def test_port_leak_detected():
    warns = detect(_df(leakage_only=True), split="temporal")
    assert any(w["rule"] == "port_leak" and "dst_port" in w["columns"] for w in warns)


def test_target_leak_detected():
    df = _df()
    df["attack_type"] = df["label"].map({"BENIGN": "none", "DDoS": "ddos"})
    rules = {w["rule"] for w in detect(df, split="temporal")}
    assert "target_leak" in rules


def test_clean_data_has_fewer_warnings():
    df = _df().drop(columns=["flow_id", "timestamp"])
    warns = detect(df, split="temporal")
    assert not any(w["rule"] in {"id_leak", "time_leak"} for w in warns)
