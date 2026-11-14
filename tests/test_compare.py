import pytest

from flowlab.compare import MAX_RUNS, MIN_RUNS, build_comparison


def _record(
    run_id: str,
    *,
    dataset_hash: str = "same",
    features: tuple[str, ...] = ("bytes_per_s", "dst_port"),
    split: str = "temporal",
    seed: int = 42,
    test: int = 30,
    validation_auc: float = 0.90,
    test_auc: float = 0.92,
    f1: float = 0.86,
    recall: float = 0.84,
    fpr: float = 0.04,
) -> dict:
    payload = {
        "best_model": "mlp",
        "results": [
            {
                "model": "mlp",
                "kind": "supervised",
                "validation_metrics": {"auc": validation_auc},
                "metrics": {
                    "auc": test_auc,
                    "pr_auc": test_auc - 0.02,
                    "f1": f1,
                    "precision": f1 - 0.01,
                    "recall": recall,
                    "fpr": fpr,
                    "attack_support": 10,
                },
                "confusion": {"tn": 18, "fp": 2, "fn": 2, "tp": 8},
                "duration_s": 0.1,
                "threshold": 0.5,
                "threshold_source": "fixed",
            }
        ],
        "dataset": {
            "source": "flows.csv",
            "hash": dataset_hash,
            "split": split,
            "seed": seed,
            "rows": 100,
            "train": 50,
            "validation": 20,
            "test": test,
            "attack_test": 10,
            "threshold": 0.5,
            "features": {"used": list(features), "encoded": len(features) + 1},
        },
        "experiment_fingerprint": f"fingerprint-{run_id}",
    }
    return {
        "id": run_id,
        "created_at": "2026-11-15T09:00:00+08:00",
        "source": "flows.csv",
        "dataset_hash": dataset_hash,
        "split": split,
        "payload": payload,
    }


def test_comparable_runs_include_deltas_and_markdown():
    comparison = build_comparison(
        [
            _record("baseline"),
            _record("candidate", test_auc=0.95, f1=0.90, recall=0.91, fpr=0.02),
        ]
    )
    assert comparison["status"] == "comparable"
    assert comparison["comparable"] is True
    assert all(check["ok"] for check in comparison["checks"])
    assert comparison["runs"][1]["delta"]["test_auc"] == pytest.approx(0.03)
    assert comparison["runs"][1]["delta"]["fpr"] == pytest.approx(-0.02)
    assert "跨实验对比" in comparison["markdown"]
    assert "candidate" in comparison["markdown"]


def test_different_dataset_is_incompatible():
    comparison = build_comparison([_record("a"), _record("b", dataset_hash="different")])
    assert comparison["status"] == "incompatible"
    assert comparison["comparable"] is False
    assert any("数据指纹不一致" in warning for warning in comparison["warnings"])


def test_same_dataset_different_features_is_limited():
    comparison = build_comparison(
        [
            _record("a"),
            _record("b", features=("bytes_per_s", "dst_port", "protocol")),
        ]
    )
    assert comparison["status"] == "limited"
    assert any(check["key"] == "features" and not check["ok"] for check in comparison["checks"])


def test_different_validation_partition_is_limited():
    first = _record("a")
    second = _record("b")
    second["payload"]["dataset"]["validation"] = 35
    comparison = build_comparison([first, second])
    assert comparison["status"] == "limited"
    split_check = next(check for check in comparison["checks"] if check["key"] == "split")
    assert split_check["ok"] is False


def test_comparison_limits_run_count_and_rejects_duplicates():
    with pytest.raises(ValueError, match="一次只能对比"):
        build_comparison([_record("only")])
    with pytest.raises(ValueError, match="一次只能对比"):
        build_comparison([_record(str(index)) for index in range(MAX_RUNS + 1)])

    from flowlab.compare import load_comparison

    with pytest.raises(ValueError, match="不能重复"):
        load_comparison(["same", "same"])
    assert MIN_RUNS == 2
