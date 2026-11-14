import json
import sqlite3

from flowlab import store


def _payload():
    return {
        "dataset": {
            "source": "synthetic",
            "hash": "abc123",
            "split": "temporal",
            "seed": 7,
            "threshold": 0.5,
            "rows": 100,
            "train": 50,
            "validation": 20,
            "test": 30,
        },
        "experiment_fingerprint": "stable-fingerprint",
        "best_model": "stable",
        "results": [
            {
                "model": "overfit",
                "metrics": {"auc": 0.99, "attack_support": 10},
                "validation_metrics": {"auc": 0.70},
                "attack_train": 20,
                "attack_validation": 5,
            },
            {
                "model": "stable",
                "metrics": {"auc": 0.91, "attack_support": 10},
                "validation_metrics": {"auc": 0.93},
                "attack_train": 20,
                "attack_validation": 5,
            },
        ],
    }


def test_save_run_keeps_validation_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("FLOWLAB_HOME", str(tmp_path))
    run_id = store.save_run(_payload())
    record = store.get_run(run_id)
    assert record["best_model"] == "stable"
    assert record["best_auc"] == 0.91
    assert record["best_validation_auc"] == 0.93
    assert store.list_runs()[0]["models"] == ["overfit", "stable"]


def test_legacy_database_is_migrated_in_place(tmp_path, monkeypatch):
    monkeypatch.setenv("FLOWLAB_HOME", str(tmp_path))
    db = tmp_path / "flowlab.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """CREATE TABLE runs (
              id TEXT PRIMARY KEY, created_at TEXT NOT NULL, source TEXT,
              dataset_hash TEXT, split TEXT, seed INTEGER, threshold REAL,
              rows INTEGER, train INTEGER, test INTEGER, attack_train INTEGER,
              attack_test INTEGER, best_model TEXT, best_auc REAL, payload TEXT NOT NULL
            )"""
        )
        conn.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy",
                "2026-01-01T00:00:00",
                "old.csv",
                "oldhash",
                "temporal",
                42,
                0.5,
                100,
                70,
                30,
                10,
                5,
                "mlp",
                0.9,
                json.dumps({"dataset": {}, "results": []}),
            ),
        )
    runs = store.list_runs()
    assert runs[0]["id"] == "legacy"
    assert runs[0]["schema_version"] == 1
    with store.connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)")}
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert "validation" in columns
    assert version == store.SCHEMA_VERSION


def test_delete_run(tmp_path, monkeypatch):
    monkeypatch.setenv("FLOWLAB_HOME", str(tmp_path))
    run_id = store.save_run(_payload())
    assert store.delete_run(run_id) is True
    assert store.delete_run(run_id) is False
    assert store.get_run(run_id) is None
