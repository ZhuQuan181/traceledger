import time

from fastapi.testclient import TestClient

from flowlab.api.main import PICKLE_TOKEN, app

client = TestClient(app, base_url="http://127.0.0.1:8765")


def test_health_is_local_and_has_no_cors_allow_origin():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert "access-control-allow-origin" not in res.headers
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"


def test_cross_site_write_is_rejected():
    res = client.post(
        "/api/demo",
        json={"normal": 200, "attack": 30, "models": ["mlp"], "save": False},
        headers={"Origin": "https://evil.example"},
    )
    assert res.status_code == 403
    assert "拒绝跨站请求" in res.json()["detail"]


def test_cross_site_fetch_metadata_is_rejected_without_origin():
    res = client.post(
        "/api/demo",
        json={"normal": 200, "attack": 30, "models": ["mlp"], "save": False},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert res.status_code == 403


def test_same_origin_demo_runs():
    res = client.post(
        "/api/demo",
        json={"normal": 200, "attack": 30, "models": ["mlp"], "save": False},
        headers={"Origin": "http://127.0.0.1:8765"},
    )
    assert res.status_code == 200
    assert res.json()["dataset"]["rows"] == 230


def test_target_fpr_mode_is_accepted_and_recorded():
    res = client.post(
        "/api/demo",
        json={
            "normal": 300,
            "attack": 50,
            "models": ["mlp"],
            "threshold_mode": "fpr",
            "target_fpr": 0.05,
            "save": False,
        },
        headers={"Origin": "http://127.0.0.1:8765"},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["dataset"]["threshold_source"] == "validation_fpr"
    assert payload["dataset"]["threshold_target_fpr"] == 0.05


def test_same_host_different_port_is_rejected():
    res = client.post(
        "/api/demo",
        json={"normal": 200, "attack": 30, "models": ["mlp"], "save": False},
        headers={"Origin": "http://127.0.0.1:9999"},
    )
    assert res.status_code == 403


def test_untrusted_host_is_rejected_even_when_origin_matches():
    res = client.post(
        "/api/demo",
        json={"normal": 100, "attack": 10, "models": ["iforest"], "save": False},
        headers={"Host": "evil.example", "Origin": "http://evil.example"},
    )
    assert res.status_code == 403
    assert "不受信任的 Host" in res.json()["detail"]


def test_explicit_allowed_host_supports_reverse_proxy(monkeypatch):
    monkeypatch.setenv("FLOWLAB_ALLOWED_HOSTS", "flowlab.example")
    res = client.get("/api/health", headers={"Host": "flowlab.example"})
    assert res.status_code == 200


def test_history_query_bounds_are_validated():
    assert client.get("/api/history?limit=-1").status_code == 422
    assert client.delete("/api/history?keep=0").status_code == 422


def test_history_supports_search_filters_and_annotation(monkeypatch, tmp_path):
    from flowlab.store import save_run

    monkeypatch.setenv("FLOWLAB_HOME", str(tmp_path))
    payload = {
        "dataset": {
            "source": "alpha.csv",
            "hash": "abc",
            "split": "temporal",
            "seed": 42,
            "threshold": 0.5,
            "rows": 100,
            "train": 60,
            "validation": 20,
            "test": 20,
        },
        "best_model": "mlp",
        "experiment_fingerprint": "fp",
        "results": [
            {
                "model": "mlp",
                "metrics": {"auc": 0.9, "attack_support": 5},
                "validation_metrics": {"auc": 0.88},
            }
        ],
    }
    run_id = save_run(payload)
    res = client.get("/api/history?q=alpha&model=mlp&status=unreviewed")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["runs"][0]["id"] == run_id
    assert body["db_bytes"] > 0

    patch = client.patch(
        f"/api/history/{run_id}",
        json={"note": "baseline", "status": "baseline"},
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "baseline"
    assert client.get("/api/history?q=baseline").json()["total"] == 1


def test_large_history_response_uses_gzip(monkeypatch, tmp_path):
    from flowlab.store import save_run

    monkeypatch.setenv("FLOWLAB_HOME", str(tmp_path))
    run_id = save_run(
        {
            "dataset": {"source": "large.csv", "hash": "large"},
            "best_model": None,
            "results": [],
            "report_md": "diagnostic detail\n" * 4000,
            "report_html": "<html><body>" + "<p>diagnostic detail</p>" * 1000 + "</body></html>",
        }
    )
    res = client.get(
        f"/api/history/{run_id}",
        headers={"Accept-Encoding": "gzip"},
    )
    assert res.status_code == 200
    assert res.headers["content-encoding"] == "gzip"
    assert res.json()["dataset"]["source"] == "large.csv"


def test_history_annotation_rejects_empty_patch(monkeypatch, tmp_path):
    from flowlab.store import save_run

    monkeypatch.setenv("FLOWLAB_HOME", str(tmp_path))
    run_id = save_run(
        {
            "dataset": {"source": "x", "hash": "h"},
            "best_model": None,
            "results": [],
        }
    )
    res = client.patch(f"/api/history/{run_id}", json={})
    assert res.status_code == 400


def test_compare_requires_two_ids():
    res = client.get("/api/compare?ids=only-one")
    assert res.status_code == 400
    assert "2–4" in res.json()["detail"]


def test_compare_returns_the_shared_structure(monkeypatch):
    import flowlab.api.main as api_main

    payload = {
        "status": "comparable",
        "comparable": True,
        "runs": [],
        "checks": [],
        "warnings": [],
        "markdown": "# 对比",
    }
    monkeypatch.setattr(api_main, "load_comparison", lambda ids: {**payload, "ids": ids})
    res = client.get("/api/compare?ids=one,two")
    assert res.status_code == 200
    assert res.json()["ids"] == ["one", "two"]
    assert res.json()["status"] == "comparable"


def test_session_token_is_not_cors_exposed():
    res = client.get("/api/session", headers={"Origin": "https://evil.example"})
    assert res.status_code == 200
    assert res.json()["pickle_token"] == PICKLE_TOKEN
    assert "access-control-allow-origin" not in res.headers


def test_pickle_upload_requires_session_token():
    res = client.post(
        "/api/upload",
        files={"file": ("unsafe.pkl", b"not a pickle", "application/octet-stream")},
        data={"allow_pickle": "true", "models": "mlp", "save": "false"},
    )
    assert res.status_code == 403
    assert "会话令牌" in res.json()["detail"]


def test_pickle_upload_with_token_reaches_content_validation():
    res = client.post(
        "/api/upload",
        files={"file": ("unsafe.pkl", b"not a pickle", "application/octet-stream")},
        data={"allow_pickle": "true", "models": "mlp", "save": "false"},
        headers={"X-FlowLab-Pickle-Token": PICKLE_TOKEN},
    )
    assert res.status_code == 400
    assert "读取失败" in res.json()["detail"]


def test_invalid_ablation_is_a_client_error():
    res = client.post(
        "/api/demo",
        json={
            "normal": 200,
            "attack": 30,
            "models": ["mlp"],
            "ablate": "label",
            "save": False,
        },
        headers={"Origin": "http://127.0.0.1:8765"},
    )
    assert res.status_code == 400
    assert "没有参与训练" in res.json()["detail"]


def test_preflight_returns_mapping_and_split_coverage():
    from flowlab.synthetic import generate

    raw = generate(180, 30, seed=12)
    res = client.post(
        "/api/preflight",
        files={"file": ("flows.csv", raw.to_csv(index=False).encode(), "text/csv")},
        data={"split": "temporal", "test_size": "0.3", "validation_size": "0.2"},
    )
    assert res.status_code == 200
    report = res.json()
    assert report["ready_for_evaluation"] is True
    assert report["labels"]["attack"] == 30
    assert report["split"]["coverage"][0]["attack"] > 0
    mapped = {row["original"]: row for row in report["column_mapping"]}
    assert mapped["Source IP"]["canonical"] == "src_ip"
    assert res.headers["cache-control"] == "no-store"


def test_preflight_allows_scoring_when_upload_has_no_labels():
    from flowlab.synthetic import generate

    raw = generate(120, 20, seed=13).drop(columns=["Label"])
    res = client.post(
        "/api/preflight",
        files={"file": ("unlabeled.csv", raw.to_csv(index=False).encode(), "text/csv")},
    )
    assert res.status_code == 200
    report = res.json()
    assert report["ready_for_evaluation"] is False
    assert report["ready_for_scoring"] is True
    assert report["labels"]["present"] is False


def test_background_job_reports_progress_and_persists_result(monkeypatch, tmp_path):
    monkeypatch.setenv("FLOWLAB_HOME", str(tmp_path))
    created = client.post(
        "/api/jobs/demo",
        json={
            "normal": 240,
            "attack": 40,
            "models": ["iforest"],
            "save": True,
        },
        headers={"Origin": "http://127.0.0.1:8765"},
    )
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    assert created.json()["status"] in {"queued", "running"}

    deadline = time.monotonic() + 20
    final = None
    while time.monotonic() < deadline:
        res = client.get(f"/api/jobs/{job_id}")
        assert res.status_code == 200
        job = res.json()
        assert job["percent"] <= 100
        if job["status"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            final = job
            break
        time.sleep(0.03)

    assert final is not None, "后台任务未在 20 秒内完成"
    assert final["status"] == "succeeded", final.get("error")
    assert final["percent"] == 100
    assert final["phase"] == "done"
    assert final["run_id"]
    saved = client.get(f"/api/history/{final['run_id']}")
    assert saved.status_code == 200
    assert saved.json()["dataset"]["rows"] == 280


def test_background_job_unknown_id_is_404_and_finished_job_cannot_cancel():
    assert client.get("/api/jobs/not-a-job").status_code == 404
    assert client.delete("/api/jobs/not-a-job").status_code == 404


def test_unlabeled_score_job_returns_ranked_flows():
    from flowlab.schema import normalize_columns
    from flowlab.synthetic import generate

    frame = normalize_columns(generate(300, 40, seed=9)).drop(columns=["label"])
    created = client.post(
        "/api/jobs/score",
        files={"file": ("flows.csv", frame.to_csv(index=False).encode(), "text/csv")},
        data={"model": "iforest", "top": "10"},
        headers={"Origin": "http://127.0.0.1:8765"},
    )
    assert created.status_code == 202
    job_id = created.json()["job_id"]

    deadline = time.monotonic() + 20
    final = None
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            final = job
            break
        time.sleep(0.03)
    assert final is not None and final["status"] == "succeeded", final
    assert final["result_available"] is True

    result = client.get(f"/api/jobs/{job_id}/result")
    assert result.status_code == 200
    payload = result.json()
    assert payload["mode"] == "score"
    assert payload["dataset"]["rows"] == 340
    assert len(payload["top"]) == 10
    scores = [row["score"] for row in payload["top"]]
    assert scores == sorted(scores, reverse=True)


def test_score_job_rejects_a_supervised_model():
    res = client.post(
        "/api/jobs/score",
        files={"file": ("flows.csv", b"a,b\n1,2\n", "text/csv")},
        data={"model": "mlp"},
    )
    assert res.status_code == 400
    assert "无监督模型" in res.json()["detail"]


def test_job_status_and_unpersisted_result_survive_api_restart(monkeypatch, tmp_path):
    import flowlab.api.main as api_main
    from flowlab.jobs import JobManager

    monkeypatch.setenv("FLOWLAB_HOME", str(tmp_path / "restart-home"))
    first = JobManager(owner_id="before-api-restart")
    try:
        created = first.submit(
            "score",
            model_count=1,
            has_ablation=False,
            save=False,
            runner=lambda progress, cancel: {
                "mode": "score",
                "top": [{"flow_id": "flow-42", "score": 0.88}],
            },
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if first.get(created["job_id"])["status"] == "succeeded":
                break
            time.sleep(0.01)
        assert first.get(created["job_id"])["status"] == "succeeded"
    finally:
        first.shutdown(wait=True)

    restarted = JobManager(owner_id="after-api-restart")
    monkeypatch.setattr(api_main, "JOBS", restarted)
    try:
        status = client.get(f"/api/jobs/{created['job_id']}")
        assert status.status_code == 200
        assert status.json()["status"] == "succeeded"
        assert status.json()["result_available"] is True

        result = client.get(f"/api/jobs/{created['job_id']}/result")
        assert result.status_code == 200
        assert result.json()["top"][0]["flow_id"] == "flow-42"
    finally:
        restarted.shutdown(wait=True)
