import numpy as np
import pandas as pd

from flowlab.engineer import add_engineered_features
from flowlab.preflight import preflight_frame
from flowlab.schema import normalize_columns
from flowlab.synthetic import generate


def _frame(rows: int = 300, attacks: int = 60) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = generate(n_normal=rows, n_attack=attacks, seed=7)
    return raw, add_engineered_features(normalize_columns(raw))


def test_preflight_explains_column_mapping_and_split_coverage():
    raw, df = _frame()
    report = preflight_frame(
        df,
        source="flows.csv",
        raw_columns=list(raw.columns),
        split="temporal",
    )

    assert report["ready_for_evaluation"] is True
    assert report["ready_for_scoring"] is True
    assert report["dataset"]["rows"] == len(df)
    mapping = {row["original"]: row for row in report["column_mapping"]}
    assert mapping["Source IP"]["canonical"] == "src_ip"
    assert mapping["Source IP"]["mapped"] is True
    assert mapping["Source IP"]["role"] == "源 IP"
    assert report["labels"]["benign"] == 300
    assert report["labels"]["attack"] == 60
    assert report["split"]["effective"] == "temporal"
    assert [row["split"] for row in report["split"]["coverage"]] == [
        "train",
        "validation",
        "test",
    ]
    assert all(row["benign"] > 0 and row["attack"] > 0 for row in report["split"]["coverage"])


def test_preflight_blocks_evaluation_but_not_scoring_without_labels():
    _, df = _frame()
    report = preflight_frame(df.drop(columns=["label"]), source="unlabeled.csv")

    assert report["ready_for_evaluation"] is False
    assert report["ready_for_scoring"] is True
    assert any("没有 label" in blocker for blocker in report["blockers"]["evaluation"])
    label_check = next(check for check in report["checks"] if check["key"] == "labels")
    assert label_check["status"] == "fail"
    assert label_check["scope"] == "evaluation"


def test_preflight_warns_when_temporal_split_will_fall_back():
    _, df = _frame()
    df["timestamp"] = "not-a-timestamp"
    report = preflight_frame(df, source="bad-time.csv", split="temporal")

    assert report["ready_for_evaluation"] is True
    assert report["timestamp"]["parse_rate"] == 0.0
    assert report["split"]["fell_back"] is True
    assert report["split"]["effective"] == "random"
    timestamp = next(check for check in report["checks"] if check["key"] == "timestamp")
    assert timestamp["status"] == "warn"


def test_preflight_flags_missing_and_infinite_features():
    _, df = _frame()
    df.loc[df.index[:4], "bytes_per_s"] = np.inf
    df.loc[df.index[:3], "packets_per_s"] = np.nan
    report = preflight_frame(df, source="dirty.csv")

    assert report["non_finite"]["cells"] == 4
    assert report["non_finite"]["columns"]["bytes_per_s"] == 4
    assert report["missing"]["cells"] >= 3
    assert any(row["column"] == "packets_per_s" for row in report["missing"]["columns"])


def test_preflight_detects_columns_that_collapse_to_the_same_schema_name():
    raw, df = _frame()
    duplicate = df.copy()
    duplicate["source_ip"] = duplicate["src_ip"]
    normalized = normalize_columns(duplicate)
    report = preflight_frame(
        normalized,
        source="collision.csv",
        raw_columns=[*raw.columns, "src_ip"],
    )

    collision = next(check for check in report["checks"] if check["key"] == "column_collision")
    assert collision["status"] == "warn"
    assert "src_ip" in collision["detail"]
