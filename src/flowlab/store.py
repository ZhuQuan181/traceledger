"""实验历史：本地 SQLite，不上传、不联网。

位置：$FLOWLAB_HOME/flowlab.db（默认 ~/.flowlab/flowlab.db）
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2
SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id            TEXT PRIMARY KEY,
  schema_version INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT NOT NULL,
  source        TEXT,
  dataset_hash  TEXT,
  split         TEXT,
  seed          INTEGER,
  threshold     REAL,
  rows          INTEGER,
  train         INTEGER,
  validation    INTEGER,
  test          INTEGER,
  attack_train  INTEGER,
  attack_validation INTEGER,
  attack_test   INTEGER,
  best_model    TEXT,
  best_auc      REAL,
  best_validation_auc REAL,
  models        TEXT,
  fingerprint   TEXT,
  payload       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
"""

MIGRATION_COLUMNS = {
    "schema_version": "INTEGER NOT NULL DEFAULT 1",
    "validation": "INTEGER",
    "attack_validation": "INTEGER",
    "best_validation_auc": "REAL",
    "models": "TEXT",
    "fingerprint": "TEXT",
}


def db_path() -> Path:
    home = Path(os.environ.get("FLOWLAB_HOME", Path.home() / ".flowlab"))
    home.mkdir(parents=True, exist_ok=True)
    return home / "flowlab.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
    for name, definition in MIGRATION_COLUMNS.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {name} {definition}")
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return conn


def save_run(payload: dict) -> str:
    """存一份前端同构的 payload，返回 run id。"""
    results = payload.get("results") or []
    best_model = payload.get("best_model")
    best = next((r for r in results if r.get("model") == best_model), None)
    if best is None and results:
        best = max(
            results,
            key=lambda r: (r.get("validation_metrics") or {}).get("auc") or -1,
        )
    ds = payload.get("dataset") or {}
    rid = uuid.uuid4().hex[:10]
    with connect() as conn:
        conn.execute(
            """INSERT INTO runs (
              id, schema_version, created_at, source, dataset_hash, split, seed,
              threshold, rows, train, validation, test, attack_train,
              attack_validation, attack_test, best_model, best_auc,
              best_validation_auc, models, fingerprint, payload
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rid,
                SCHEMA_VERSION,
                datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                ds.get("source"),
                ds.get("hash"),
                ds.get("split"),
                ds.get("seed", 42),
                ds.get("threshold"),
                ds.get("rows"),
                ds.get("train"),
                ds.get("validation"),
                ds.get("test"),
                (results[0].get("attack_train") if results else 0),
                (results[0].get("attack_validation") if results else 0),
                (best["metrics"].get("attack_support") if best else 0),
                best_model or (best["model"] if best else None),
                best["metrics"].get("auc") if best else None,
                ((best.get("validation_metrics") or {}).get("auc") if best else None),
                json.dumps(
                    [row.get("model") for row in results if row.get("model")],
                    ensure_ascii=False,
                ),
                payload.get("experiment_fingerprint"),
                json.dumps(payload, ensure_ascii=False),
            ),
        )
    return rid


def list_runs(limit: int = 20) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id,schema_version,created_at,source,dataset_hash,split,rows,"
            "validation,best_model,best_auc,best_validation_auc,models,fingerprint "
            "FROM runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["models"] = json.loads(item["models"]) if item.get("models") else []
        out.append(item)
    return out


def get_run(run_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    out = dict(row)
    out["payload"] = json.loads(out["payload"])
    return out


def compare(run_ids: list[str]) -> list[dict]:
    rows = []
    for rid in run_ids:
        r = get_run(rid)
        if r:
            rows.append(r)
    return rows


def delete_run(run_id: str) -> bool:
    with connect() as conn:
        deleted = conn.execute("DELETE FROM runs WHERE id = ?", (run_id,)).rowcount
    return bool(deleted)


def count() -> int:
    with connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0])


def prune(keep: int = 50) -> int:
    """只保留最近 keep 条，返回删除条数。"""
    if keep < 1:
        raise ValueError("keep 至少为 1（想清空请用 keep=1 并自行触发）")
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM runs ORDER BY created_at DESC LIMIT -1 OFFSET ?", (keep,)
        ).fetchall()
        ids = [(r["id"],) for r in rows]
        if ids:
            conn.executemany("DELETE FROM runs WHERE id = ?", ids)
    return len(ids)
