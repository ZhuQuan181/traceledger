from fastapi.testclient import TestClient

from flowlab.api.main import PICKLE_TOKEN, app

client = TestClient(app)


def test_health_is_local_and_has_no_cors_allow_origin():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert "access-control-allow-origin" not in res.headers


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
        headers={"Origin": "http://testserver"},
    )
    assert res.status_code == 200
    assert res.json()["dataset"]["rows"] == 230


def test_same_host_different_port_is_rejected():
    res = client.post(
        "/api/demo",
        json={"normal": 200, "attack": 30, "models": ["mlp"], "save": False},
        headers={"Origin": "http://testserver:9999"},
    )
    assert res.status_code == 403


def test_history_query_bounds_are_validated():
    assert client.get("/api/history?limit=-1").status_code == 422
    assert client.delete("/api/history?keep=0").status_code == 422


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
        headers={"Origin": "http://testserver"},
    )
    assert res.status_code == 400
    assert "没有参与训练" in res.json()["detail"]
