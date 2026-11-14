import pandas as pd

from flowlab.quality import RARE_CLASS_THRESHOLD, label_quality


def test_label_quality_finds_duplicates_conflicts_and_rare_classes():
    df = pd.DataFrame(
        {
            "flow_id": ["a", "a", "b", "b", "c", "c"],
            "src_ip": ["10.0.0.1", "10.0.0.1", "10.0.0.2", "10.0.0.2", "10.0.0.3", "10.0.0.3"],
            "dst_port": [80, 80, 443, 443, 443, 443],
            "label": ["BENIGN", "DDoS", "BENIGN", "BENIGN", "RareAttack", "RareAttack"],
        }
    )
    quality = label_quality(
        df, test_by_label=[{"label": "RareAttack", "kind": "attack", "total": 3}]
    )
    assert quality["missing_labels"] == 0
    assert quality["duplicate_rows"] == 4
    assert quality["conflict_key"] == "flow_id"
    assert quality["conflict_groups"] == 1
    assert quality["conflict_rows"] == 2
    assert quality["conflict_examples"][0]["labels"] == ["BENIGN", "DDoS"]
    assert {row["label"] for row in quality["rare_classes"]} == {
        "BENIGN",
        "DDoS",
        "RareAttack",
    }
    assert quality["rare_test_labels"] == [{"label": "RareAttack", "total": 3}]
    assert RARE_CLASS_THRESHOLD == 20


def test_label_quality_counts_duplicate_rows_and_missing_labels():
    df = pd.DataFrame(
        {
            "src_ip": ["10.0.0.1", "10.0.0.1", "10.0.0.2"],
            "label": ["BENIGN", "BENIGN", None],
        }
    )
    quality = label_quality(df)
    assert quality["missing_labels"] == 1
    assert quality["duplicate_rows"] == 2
    assert quality["conflict_groups"] == 0


def test_missing_label_column_returns_empty_quality():
    assert label_quality(pd.DataFrame({"x": [1, 2]})) == {}


def test_benign_aliases_are_not_reported_as_label_conflicts():
    df = pd.DataFrame(
        {
            "flow_id": ["same", "same"],
            "value": [1, 2],
            "label": ["BENIGN", "normal"],
        }
    )
    quality = label_quality(df)
    assert quality["conflict_key"] == "flow_id"
    assert quality["conflict_groups"] == 0


def test_default_synthetic_flow_ids_are_unique_and_quality_is_clean():
    from flowlab.schema import normalize_columns
    from flowlab.synthetic import generate

    df = normalize_columns(generate(n_normal=800, n_attack=120, seed=42))
    quality = label_quality(df)
    assert df["flow_id"].nunique() == len(df)
    assert quality["duplicate_rows"] == 0
    assert quality["conflict_groups"] == 0
