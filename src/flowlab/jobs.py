"""本地实验任务队列。

只允许一个实验真正执行、最多再排一个，避免本机 CPU 与内存被多个
scikit-learn 任务同时抢占。任务状态写入本地 SQLite，进程重启后可将
悬空任务标为中断；实验正文写入历史库，无标签评分结果短期留在任务表。
"""

from __future__ import annotations

import atexit
import json
import logging
import shutil
import sqlite3
import tempfile
import threading
import time
import uuid
import zlib
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from flowlab.errors import ExperimentCancelled
from flowlab.store import connect, db_path, save_run

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"queued", "running", "cancelling"}
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "interrupted"}
RESULT_CODEC = "zlib-json-v1"

PHASE_LABELS = {
    "loading": "读取数据",
    "validating": "校验数据与参数",
    "features": "切分与特征准备",
    "model": "训练与评分",
    "ablation": "消融复核",
    "report": "生成报告",
    "done": "完成",
}

PHASE_BOUNDS = {
    "loading": (0, 8),
    "validating": (8, 12),
    "features": (12, 28),
    "model": (28, 80),
    "ablation": (80, 92),
    "report": (92, 99),
}

ProgressCallback = Callable[[str, int, int], None]
CancelCallback = Callable[[], bool]
JobRunner = Callable[[ProgressCallback, CancelCallback], dict]


class JobQueueFull(RuntimeError):
    """本机已经有一个任务在运行，另一个在等待。"""


class JobNotCancellable(RuntimeError):
    """任务已经结束，不能再取消。"""


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass
class Job:
    job_id: str
    kind: str
    model_count: int
    has_ablation: bool
    save: bool
    workdir: Path | None = None
    status: str = "queued"
    phase: str = "queued"
    completed_models: int = 0
    total_models: int = 0
    percent: int = 0
    message: str = "等待本机执行位"
    error: str | None = None
    run_id: str | None = None
    result: dict | None = field(default=None, repr=False)
    created_at: str = field(default_factory=now_iso)
    started_at: str | None = None
    finished_at: str | None = None
    _started_mono: float | None = None
    _elapsed_s: float = 0.0
    _result_persisted: bool = field(default=False, repr=False)
    _db_path: Path | None = field(default=None, repr=False)
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    _future: Future | None = field(default=None, repr=False)

    @property
    def active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def elapsed(self) -> float:
        if self._started_mono is None:
            return self._elapsed_s
        if self.status in TERMINAL_STATUSES:
            return self._elapsed_s
        return max(self._elapsed_s, time.monotonic() - self._started_mono)

    def snapshot(self) -> dict:
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "status": self.status,
            "phase": self.phase,
            "completed_models": self.completed_models,
            "total_models": self.total_models,
            "percent": self.percent,
            "message": self.message,
            "elapsed_s": round(self.elapsed(), 1),
            "run_id": self.run_id,
            "error": self.error,
            "has_ablation": self.has_ablation,
            "result_available": self.result is not None or self._result_persisted,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class JobManager:
    """线程安全的本机单执行位任务队列。"""

    def __init__(
        self,
        *,
        max_active: int = 2,
        ttl_s: float = 30 * 60,
        executor: ThreadPoolExecutor | None = None,
        owner_id: str | None = None,
    ) -> None:
        if max_active < 1:
            raise ValueError("max_active 至少为 1")
        self.max_active = max_active
        self.ttl_s = ttl_s
        self.owner_id = owner_id or uuid.uuid4().hex
        self._jobs: dict[str, Job] = {}
        self._lock = threading.RLock()
        self._loaded_paths: set[Path] = set()
        self._executor = executor or ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="flowlab-job"
        )
        self._closed = False

    def make_workdir(self) -> Path:
        return Path(tempfile.mkdtemp(prefix="flowlab-job-"))

    @staticmethod
    def _from_row(row: sqlite3.Row, path: Path) -> Job:
        return Job(
            job_id=row["job_id"],
            kind=row["kind"],
            model_count=int(row["model_count"]),
            has_ablation=bool(row["has_ablation"]),
            save=bool(row["save"]),
            workdir=Path(row["workdir"]) if row["workdir"] else None,
            status=row["status"],
            phase=row["phase"],
            completed_models=int(row["completed_models"]),
            total_models=int(row["total_models"]),
            percent=int(row["percent"]),
            message=row["message"],
            error=row["error"],
            run_id=row["run_id"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            _elapsed_s=float(row["elapsed_s"] or 0),
            _result_persisted=row["result"] is not None,
            _db_path=path,
        )

    def _ensure_loaded_locked(self) -> None:
        """载入当前 FLOWLAB_HOME 的任务快照，并收口上一个进程的悬空任务。"""
        path = db_path()
        if path in self._loaded_paths:
            return
        self._loaded_paths.add(path)
        try:
            with connect(path) as conn:
                rows = conn.execute("SELECT * FROM jobs").fetchall()
        except sqlite3.Error:
            logger.exception("无法读取持久化任务记录：%s", path)
            self._loaded_paths.discard(path)
            return

        recovered: list[Job] = []
        for row in rows:
            job_id = row["job_id"]
            if job_id in self._jobs:
                continue
            job = self._from_row(row, path)
            self._jobs[job_id] = job
            if job.active:
                recovered.append(job)

        for job in recovered:
            job.status = "interrupted"
            job.phase = "done"
            job.finished_at = now_iso()
            job.message = "服务重启，任务已中断"
            job.error = "FlowLab 服务在任务完成前重启；这次任务没有写入不完整历史。"
            self._discard(job)
            self._persist_locked(job)

    def _persist_locked(self, job: Job) -> None:
        if job._db_path is None:
            job._db_path = db_path()
        result_blob = None
        result_codec = None
        if job.result is not None and not job.save:
            try:
                raw = json.dumps(
                    job.result,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            except (TypeError, ValueError):
                logger.exception("任务 %s 的结果无法序列化；仅保留在内存中", job.job_id)
            else:
                result_blob = zlib.compress(raw, level=6)
                result_codec = RESULT_CODEC
                job._result_persisted = True

        job._elapsed_s = job.elapsed()
        try:
            with connect(job._db_path) as conn:
                conn.execute(
                    """INSERT INTO jobs (
                      job_id, kind, status, phase, model_count, has_ablation, save,
                      completed_models, total_models, percent, message, error, run_id,
                      result_codec, result, workdir, owner_id, created_at, started_at,
                      finished_at, updated_at, elapsed_s
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(job_id) DO UPDATE SET
                      kind=excluded.kind,
                      status=excluded.status,
                      phase=excluded.phase,
                      model_count=excluded.model_count,
                      has_ablation=excluded.has_ablation,
                      save=excluded.save,
                      completed_models=excluded.completed_models,
                      total_models=excluded.total_models,
                      percent=excluded.percent,
                      message=excluded.message,
                      error=excluded.error,
                      run_id=excluded.run_id,
                      result_codec=CASE
                        WHEN excluded.result IS NULL THEN jobs.result_codec
                        ELSE excluded.result_codec
                      END,
                      result=COALESCE(excluded.result, jobs.result),
                      workdir=excluded.workdir,
                      owner_id=excluded.owner_id,
                      created_at=excluded.created_at,
                      started_at=excluded.started_at,
                      finished_at=excluded.finished_at,
                      updated_at=excluded.updated_at,
                      elapsed_s=excluded.elapsed_s""",
                    (
                        job.job_id,
                        job.kind,
                        job.status,
                        job.phase,
                        job.model_count,
                        bool(job.has_ablation),
                        bool(job.save),
                        job.completed_models,
                        job.total_models,
                        job.percent,
                        job.message,
                        job.error,
                        job.run_id,
                        result_codec,
                        result_blob,
                        str(job.workdir) if job.workdir is not None else None,
                        self.owner_id,
                        job.created_at,
                        job.started_at,
                        job.finished_at,
                        now_iso(),
                        job._elapsed_s,
                    ),
                )
        except sqlite3.Error:
            logger.exception("无法持久化任务 %s 的状态", job.job_id)

    def _delete_locked(self, job: Job) -> None:
        if job._db_path is None:
            return
        try:
            with connect(job._db_path) as conn:
                conn.execute("DELETE FROM jobs WHERE job_id = ?", (job.job_id,))
        except sqlite3.Error:
            logger.exception("无法清理任务记录 %s", job.job_id)

    def _prune_locked(self) -> None:
        self._ensure_loaded_locked()
        if self.ttl_s < 0:
            return
        cutoff = time.time() - self.ttl_s
        for job_id, job in list(self._jobs.items()):
            if job.status in TERMINAL_STATUSES and job.finished_at:
                finished = datetime.fromisoformat(job.finished_at).timestamp()
                if finished < cutoff:
                    self._discard(job)
                    self._delete_locked(job)
                    self._jobs.pop(job_id, None)

    def _discard(self, job: Job) -> None:
        if job.workdir is not None:
            shutil.rmtree(job.workdir, ignore_errors=True)
            job.workdir = None

    def _finish_locked(
        self,
        job: Job,
        status: str,
        *,
        message: str,
        error: str | None = None,
    ) -> None:
        elapsed = job.elapsed()
        job.status = status
        job.phase = "done"
        job.message = message
        job.error = error
        job.finished_at = now_iso()
        job._elapsed_s = elapsed
        self._discard(job)
        self._persist_locked(job)

    def submit(
        self,
        kind: str,
        *,
        model_count: int,
        has_ablation: bool,
        save: bool,
        runner: JobRunner,
        workdir: Path | None = None,
    ) -> dict:
        with self._lock:
            if self._closed:
                raise RuntimeError("任务队列已关闭")
            self._prune_locked()
            active = [job for job in self._jobs.values() if job.active]
            if len(active) >= self.max_active:
                raise JobQueueFull("本机已有一个实验在运行、另一个在排队；请等待或先取消排队任务。")
            job = Job(
                job_id=uuid.uuid4().hex[:12],
                kind=kind,
                model_count=model_count,
                has_ablation=has_ablation,
                save=save,
                workdir=workdir,
                total_models=model_count,
                _db_path=db_path(),
            )
            self._jobs[job.job_id] = job
            self._persist_locked(job)
            snapshot = job.snapshot()
            job._future = self._executor.submit(self._run, job.job_id, runner)
        return snapshot

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            self._prune_locked()
            job = self._jobs.get(job_id)
            return None if job is None else job.snapshot()

    def result(self, job_id: str) -> dict | None:
        with self._lock:
            self._prune_locked()
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.result is None and job._result_persisted and job._db_path is not None:
                try:
                    with connect(job._db_path) as conn:
                        row = conn.execute(
                            "SELECT result_codec, result FROM jobs WHERE job_id = ?",
                            (job_id,),
                        ).fetchone()
                except sqlite3.Error:
                    logger.exception("无法读取任务结果 %s", job_id)
                    return None
                if row and row["result"] is not None:
                    if row["result_codec"] != RESULT_CODEC:
                        logger.error("任务 %s 使用了未知结果编码 %s", job_id, row["result_codec"])
                        return None
                    try:
                        job.result = json.loads(zlib.decompress(row["result"]))
                    except (json.JSONDecodeError, zlib.error, UnicodeDecodeError):
                        logger.exception("任务 %s 的结果无法解码", job_id)
                        return None
            return job.result

    def active(self) -> list[dict]:
        with self._lock:
            self._prune_locked()
            jobs = [job for job in self._jobs.values() if job.active]
            return [job.snapshot() for job in jobs]

    def can_accept(self) -> bool:
        with self._lock:
            self._prune_locked()
            return sum(job.active for job in self._jobs.values()) < self.max_active

    def cancel(self, job_id: str) -> dict:
        with self._lock:
            self._prune_locked()
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if job.status in TERMINAL_STATUSES:
                raise JobNotCancellable("实验已经结束，无法取消")
            job._cancel.set()
            if job.status == "queued":
                if job._future is not None:
                    job._future.cancel()
                self._finish_locked(job, "cancelled", message="排队任务已取消")
            else:
                job.status = "cancelling"
                job.message = "正在取消；当前模型完成后停止"
                self._persist_locked(job)
            return job.snapshot()

    def _run(self, job_id: str, runner: JobRunner) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status not in {"queued"}:
                return
            job.status = "running"
            job.phase = "loading"
            job.message = PHASE_LABELS["loading"]
            job.percent = 1
            job.started_at = now_iso()
            job._started_mono = time.monotonic()
            self._persist_locked(job)

        def progress(phase: str, completed: int, total: int) -> None:
            self._progress(job_id, phase, completed, total)

        def cancelled() -> bool:
            with self._lock:
                current = self._jobs.get(job_id)
                return current is None or current._cancel.is_set()

        try:
            if cancelled():
                raise ExperimentCancelled
            payload = runner(progress, cancelled)
            if cancelled():
                raise ExperimentCancelled

            run_id = None
            with self._lock:
                current = self._jobs.get(job_id)
                if current is not None and current.save:
                    current.phase = "report"
                    current.percent = max(current.percent, 98)
                    current.message = "写入本地历史"
                    self._persist_locked(current)
            if job.save:
                run_id = save_run(payload)

            with self._lock:
                current = self._jobs.get(job_id)
                if current is not None:
                    if not current.save:
                        current.result = payload
                    current.percent = 100
                    current.run_id = run_id
                    self._finish_locked(
                        current,
                        "succeeded",
                        message=(
                            "实验完成，结果已保存"
                            if run_id
                            else "打分完成"
                            if current.kind == "score"
                            else "实验完成"
                        ),
                    )
        except ExperimentCancelled:
            with self._lock:
                current = self._jobs.get(job_id)
                if current is not None:
                    self._finish_locked(current, "cancelled", message="实验已取消，未写入历史")
        except Exception as exc:  # noqa: BLE001 - 任务边界必须把异常转成可见状态
            logger.exception("FlowLab job %s failed", job_id)
            with self._lock:
                current = self._jobs.get(job_id)
                if current is not None:
                    self._finish_locked(
                        current,
                        "failed",
                        message="实验失败",
                        error=str(exc) or exc.__class__.__name__,
                    )

    def _progress(self, job_id: str, phase: str, completed: int, total: int) -> None:
        if phase not in PHASE_BOUNDS:
            return
        low, high = PHASE_BOUNDS[phase]
        fraction = 0.0 if total <= 0 else min(1.0, max(0.0, completed / total))
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or not job.active:
                return
            job.phase = phase
            job.completed_models = max(0, int(completed))
            job.total_models = max(1, int(total))
            job.percent = max(job.percent, min(99, int(low + (high - low) * fraction)))
            label = PHASE_LABELS.get(phase, phase)
            job.message = "正在取消；当前模型完成后停止" if job._cancel.is_set() else label
            if job._cancel.is_set():
                job.status = "cancelling"
            self._persist_locked(job)

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            self._closed = True
            for job in self._jobs.values():
                if job.active:
                    job._cancel.set()
            futures = [job._future for job in self._jobs.values() if job._future]
        for future in futures:
            future.cancel()
        self._executor.shutdown(wait=wait, cancel_futures=True)


JOBS = JobManager()
atexit.register(JOBS.shutdown)
