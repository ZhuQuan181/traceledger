import threading
import time
from pathlib import Path

import pytest

from flowlab.jobs import JobManager, JobQueueFull


def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.01)
    raise AssertionError("等待任务状态超时")


@pytest.fixture
def manager():
    queue = JobManager(max_active=2)
    yield queue
    queue.shutdown(wait=True)


def test_one_running_plus_one_queued_and_queue_limit(manager):
    gate = threading.Event()

    def runner(progress, cancel):
        progress("model", 0, 1)
        gate.wait(2)
        return {}

    first = manager.submit("test", model_count=1, has_ablation=False, save=False, runner=runner)
    wait_for(lambda: manager.get(first["job_id"])["status"] == "running")
    second = manager.submit("test", model_count=1, has_ablation=False, save=False, runner=runner)
    assert manager.get(second["job_id"])["status"] == "queued"
    with pytest.raises(JobQueueFull):
        manager.submit("test", model_count=1, has_ablation=False, save=False, runner=runner)
    gate.set()
    wait_for(lambda: len(manager.active()) == 0)


def test_queued_job_can_be_cancelled(manager):
    gate = threading.Event()

    def runner(progress, cancel):
        gate.wait(2)
        return {}

    first = manager.submit("test", model_count=1, has_ablation=False, save=False, runner=runner)
    wait_for(lambda: manager.get(first["job_id"])["status"] == "running")
    second = manager.submit("test", model_count=1, has_ablation=False, save=False, runner=runner)
    cancelled = manager.cancel(second["job_id"])
    assert cancelled["status"] == "cancelled"
    assert cancelled["message"] == "排队任务已取消"
    gate.set()
    wait_for(lambda: manager.get(first["job_id"])["status"] == "succeeded")


def test_running_job_is_cancelled_at_a_model_boundary(manager):
    def runner(progress, cancel):
        progress("model", 0, 2)
        while not cancel():
            time.sleep(0.01)
        return {}

    created = manager.submit("test", model_count=2, has_ablation=False, save=False, runner=runner)
    wait_for(lambda: manager.get(created["job_id"])["status"] == "running")
    cancelling = manager.cancel(created["job_id"])
    assert cancelling["status"] == "cancelling"
    final = wait_for(
        lambda: (
            manager.get(created["job_id"])
            if manager.get(created["job_id"])["status"] == "cancelled"
            else None
        )
    )
    assert final["run_id"] is None
    assert final["phase"] == "done"


def test_failure_and_progress_are_visible(manager):
    def runner(progress, cancel):
        progress("features", 1, 1)
        progress("model", 1, 3)
        raise ValueError("特征列不合法")

    created = manager.submit("test", model_count=3, has_ablation=False, save=False, runner=runner)
    final = wait_for(
        lambda: (
            manager.get(created["job_id"])
            if manager.get(created["job_id"])["status"] == "failed"
            else None
        )
    )
    assert final["error"] == "特征列不合法"
    assert final["percent"] >= 28
    assert final["started_at"] and final["finished_at"]


def test_workdir_is_removed_after_terminal_state(manager):
    workdir = manager.make_workdir()
    (workdir / "upload.csv").write_text("label\nBENIGN\n")

    created = manager.submit(
        "test",
        model_count=1,
        has_ablation=False,
        save=False,
        runner=lambda progress, cancel: {},
        workdir=Path(workdir),
    )
    wait_for(lambda: manager.get(created["job_id"])["status"] == "succeeded")
    assert not workdir.exists()
