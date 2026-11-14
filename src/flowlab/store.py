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

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id            TEXT PRIMARY KEY,
  created_at    TEXT NOT NULL,
  source        TEXT,
  dataset_hash  TEXT,
  split         TEXT,
  seed          INTEGER,
  threshold     REAL,
  rows          INTEGER,
  train         INTEGER,
  test          INTEGER,
  attack_train  INTEGER,
  attack_test   INTEGER,
  best_model    TEXT,
  best_auc      REAL,
  payload       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
"""


def db_path() -> Path:
    home = Path(os.environ.get("FLOWLAB_HOME", Path.home() / ".flowlab"))
    home.mkdir(parents=True, exist_ok=True)
    return home / "flowlab.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save_run(payload: dict) -> str:
    """存一份前端同构的 payload，返回 run id。"""
    results = payload.get("results") or []
    best = max(results, key=lambda r: r["metrics"].get("auc") or 0) if results else None
    ds = payload.get("dataset") or {}
    rid = uuid.uuid4().hex[:10]
    with connect() as conn:
        conn.execute(
            """INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rid,
                datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                ds.get("source"),
                ds.get("hash"),
                ds.get("split"),
                ds.get("seed", 42),
                ds.get("threshold"),
                ds.get("rows"),
                ds.get("train"),
                ds.get("test"),
                (results[0].get("attack_train") if results else 0),
                (best["metrics"].get("attack_support") if best else 0),
                best["model"] if best else None,
                best["metrics"].get("auc") if best else None,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
    return rid


def list_runs(limit: int = 20) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id,created_at,source,dataset_hash,split,rows,best_model,best_auc "
            "FROM runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


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
