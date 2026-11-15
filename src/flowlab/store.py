"""实验历史：本地 SQLite，不上传、不联网。

位置：$FLOWLAB_HOME/flowlab.db（默认 ~/.flowlab/flowlab.db）
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 5
STATUSES = ("unreviewed", "baseline", "failed", "archived")
PAYLOAD_CODEC = "zlib-json-v1"
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
  note          TEXT NOT NULL DEFAULT '',
  status        TEXT NOT NULL DEFAULT 'unreviewed',
  updated_at    TEXT,
  payload_codec TEXT NOT NULL DEFAULT 'json',
  payload_raw_bytes INTEGER,
  payload       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
  job_id           TEXT PRIMARY KEY,
  kind             TEXT NOT NULL,
  status           TEXT NOT NULL,
  phase            TEXT NOT NULL,
  model_count      INTEGER NOT NULL DEFAULT 0,
  has_ablation     INTEGER NOT NULL DEFAULT 0,
  save             INTEGER NOT NULL DEFAULT 1,
  completed_models INTEGER NOT NULL DEFAULT 0,
  total_models     INTEGER NOT NULL DEFAULT 0,
  percent          INTEGER NOT NULL DEFAULT 0,
  message          TEXT NOT NULL DEFAULT '',
  error            TEXT,
  run_id           TEXT,
  result_codec     TEXT,
  result           BLOB,
  workdir          TEXT,
  owner_id         TEXT NOT NULL,
  created_at       TEXT NOT NULL,
  started_at       TEXT,
  finished_at      TEXT,
  updated_at       TEXT NOT NULL,
  elapsed_s        REAL NOT NULL DEFAULT 0
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_status_created ON runs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_dataset_hash ON runs(dataset_hash);
CREATE INDEX IF NOT EXISTS idx_runs_best_model ON runs(best_model);
CREATE INDEX IF NOT EXISTS idx_runs_fingerprint ON runs(fingerprint);
CREATE INDEX IF NOT EXISTS idx_jobs_status_updated ON jobs(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_finished ON jobs(finished_at);
"""

MIGRATION_COLUMNS = {
    "schema_version": "INTEGER NOT NULL DEFAULT 1",
    "validation": "INTEGER",
    "attack_validation": "INTEGER",
    "best_validation_auc": "REAL",
    "models": "TEXT",
    "fingerprint": "TEXT",
    "note": "TEXT NOT NULL DEFAULT ''",
    "status": "TEXT NOT NULL DEFAULT 'unreviewed'",
    "updated_at": "TEXT",
    "payload_codec": "TEXT NOT NULL DEFAULT 'json'",
    "payload_raw_bytes": "INTEGER",
}

_models_cache: tuple[tuple[str, int, int], list[str]] | None = None
_initialized_paths: set[Path] = set()
_schema_lock = threading.Lock()


def db_path() -> Path:
    home = Path(os.environ.get("FLOWLAB_HOME", Path.home() / ".flowlab"))
    home.mkdir(parents=True, exist_ok=True)
    return home / "flowlab.db"


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -20000")
    conn.execute("PRAGMA wal_autocheckpoint = 256")
    conn.execute("PRAGMA journal_size_limit = 1048576")
    with _schema_lock:
        if target not in _initialized_paths:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
            for name, definition in MIGRATION_COLUMNS.items():
                if name not in columns:
                    conn.execute(f"ALTER TABLE runs ADD COLUMN {name} {definition}")
            conn.executescript(INDEXES)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            _initialized_paths.add(target)
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
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    raw_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stored_payload = zlib.compress(raw_payload, level=6)
    with connect() as conn:
        conn.execute(
            """INSERT INTO runs (
              id, schema_version, created_at, source, dataset_hash, split, seed,
              threshold, rows, train, validation, test, attack_train,
              attack_validation, attack_test, best_model, best_auc,
              best_validation_auc, models, fingerprint, note, status, updated_at,
              payload_codec, payload_raw_bytes, payload
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rid,
                SCHEMA_VERSION,
                now,
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
                "",
                "unreviewed",
                now,
                PAYLOAD_CODEC,
                len(raw_payload),
                stored_payload,
            ),
        )
    return rid


def _like(value: str) -> str:
    escaped = value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _history_filters(
    query: str = "", model: str | None = None, status: str | None = None
) -> tuple[list[str], list[str]]:
    conditions: list[str] = []
    params: list[str] = []
    if query.strip():
        pattern = _like(query)
        conditions.append(
            "(id LIKE ? ESCAPE '\\' OR source LIKE ? ESCAPE '\\' "
            "OR dataset_hash LIKE ? ESCAPE '\\' OR best_model LIKE ? ESCAPE '\\' "
            "OR note LIKE ? ESCAPE '\\')"
        )
        params.extend([pattern] * 5)
    if model:
        conditions.append("models LIKE ? ESCAPE '\\'")
        params.append(_like(f'"{model}"'))
    if status:
        conditions.append("status = ?")
        params.append(status)
    return conditions, params


def list_runs(
    limit: int = 20,
    offset: int = 0,
    query: str = "",
    model: str | None = None,
    status: str | None = None,
) -> list[dict]:
    conditions, params = _history_filters(query, model, status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id,schema_version,created_at,source,dataset_hash,split,rows,"
            "validation,test,threshold,best_model,best_auc,best_validation_auc,"
            "models,fingerprint,note,status,updated_at "
            f"FROM runs {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["models"] = json.loads(item["models"]) if item.get("models") else []
        out.append(item)
    return out


def count_runs(query: str = "", model: str | None = None, status: str | None = None) -> int:
    conditions, params = _history_filters(query, model, status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with connect() as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM runs {where}", params).fetchone()[0])


def _parse_models(rows: list[sqlite3.Row]) -> list[str]:
    names: set[str] = set()
    for row in rows:
        try:
            names.update(str(value) for value in json.loads(row["models"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return sorted(names)


def history_models() -> list[str]:
    global _models_cache
    path = db_path()
    with connect() as conn:
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
        if _models_cache is not None and _models_cache[0] == key:
            return list(_models_cache[1])
        rows = conn.execute("SELECT models FROM runs WHERE models IS NOT NULL").fetchall()
    result = _parse_models(rows)
    _models_cache = (key, result)
    return list(result)


def stats() -> dict:
    path = db_path()
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count, "
            "COALESCE(SUM(LENGTH(payload)), 0) AS payload_bytes, "
            "COALESCE(SUM(COALESCE(payload_raw_bytes, LENGTH(payload))), 0) AS payload_raw_bytes "
            "FROM runs"
        ).fetchone()
    wal_path = path.with_name(path.name + "-wal")
    file_bytes = path.stat().st_size if path.exists() else 0
    wal_bytes = wal_path.stat().st_size if wal_path.exists() else 0
    return {
        "count": int(row["count"]),
        "db_bytes": file_bytes + wal_bytes,
        "wal_bytes": wal_bytes,
        "payload_bytes": int(row["payload_bytes"]),
        "payload_raw_bytes": int(row["payload_raw_bytes"]),
    }


def history_page(
    limit: int = 20,
    offset: int = 0,
    query: str = "",
    model: str | None = None,
    status: str | None = None,
) -> dict:
    """一次连接返回历史列表、计数和容量摘要，避免同一页面重复扫描数据库。"""
    conditions, params = _history_filters(query, model, status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id,schema_version,created_at,source,dataset_hash,split,rows,"
            "validation,test,threshold,best_model,best_auc,best_validation_auc,"
            "models,fingerprint,note,status,updated_at "
            f"FROM runs {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        total = int(conn.execute(f"SELECT COUNT(*) FROM runs {where}", params).fetchone()[0])
        available = int(conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0])
        payload_row = conn.execute(
            "SELECT COALESCE(SUM(LENGTH(payload)), 0) AS stored, "
            "COALESCE(SUM(COALESCE(payload_raw_bytes, LENGTH(payload))), 0) AS raw "
            "FROM runs"
        ).fetchone()
        model_rows = conn.execute("SELECT models FROM runs WHERE models IS NOT NULL").fetchall()
    runs = []
    for row in rows:
        item = dict(row)
        item["models"] = json.loads(item["models"]) if item.get("models") else []
        runs.append(item)
    db = db_path()
    wal = db.with_name(db.name + "-wal")
    db_bytes = (db.stat().st_size if db.exists() else 0) + (
        wal.stat().st_size if wal.exists() else 0
    )
    return {
        "runs": runs,
        "total": total,
        "available": available,
        "db_bytes": db_bytes,
        "wal_bytes": wal.stat().st_size if wal.exists() else 0,
        "payload_bytes": int(payload_row["stored"]),
        "payload_raw_bytes": int(payload_row["raw"]),
        "models": _parse_models(model_rows),
    }


def get_run(run_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    out = dict(row)
    stored = out["payload"]
    if isinstance(stored, bytes):
        raw = zlib.decompress(stored)
    else:
        raw = str(stored).encode("utf-8")
    out["payload"] = json.loads(raw)
    return out


def update_run(
    run_id: str,
    *,
    note: str | None = None,
    status: str | None = None,
) -> dict | None:
    if status is not None and status not in STATUSES:
        raise ValueError(f"status 只能是 {STATUSES}")
    updates: list[str] = []
    params: list[str] = []
    if note is not None:
        updates.append("note = ?")
        params.append(note.strip()[:500])
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if not updates:
        raise ValueError("至少提供 note 或 status")
    updates.append("updated_at = ?")
    params.append(datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"))
    params.append(run_id)
    with connect() as conn:
        changed = conn.execute(
            f"UPDATE runs SET {', '.join(updates)} WHERE id = ?", params
        ).rowcount
    return get_run(run_id) if changed else None


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
    if ids:
        with sqlite3.connect(db_path()) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("VACUUM")
    return len(ids)
