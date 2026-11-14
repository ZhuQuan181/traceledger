"""本地 API：薄层，编排全在 service.execute()。

启动：uv run flowlab serve  →  http://127.0.0.1:8765
"""
from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from flowlab.models.registry import available
from flowlab.pipeline import load_frame
from flowlab.service import ExperimentSpec, demo_frame, execute
from flowlab.store import get_run, list_runs, save_run

app = FastAPI(title="FlowLab", version="0.4.0")

PICKLE_TOKEN = secrets.token_urlsafe(32)
MAX_UPLOAD_BYTES = int(os.getenv("FLOWLAB_MAX_UPLOAD_MB", "1024")) * 1024 * 1024
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _same_origin(origin: str, request: Request) -> bool:
    """只信任同源页面；兼容 Vite 代理与本机回环别名。"""
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"}:
        return False
    origin_host = (parsed.hostname or "").lower()
    request_host = (request.url.hostname or "").lower()
    if not origin_host or not request_host:
        return False
    if origin_host == request_host:
        return True
    loopback = {"localhost", "127.0.0.1", "::1"}
    return origin_host in loopback and request_host in loopback


@app.middleware("http")
async def reject_cross_site_writes(request: Request, call_next):
    """阻止网页跨站触发写操作；无 Origin 的 CLI/curl 调用不受影响。"""
    if request.method in MUTATING_METHODS and request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        if (request.headers.get("sec-fetch-site") == "cross-site"
                or (origin and not _same_origin(origin, request))):
            return JSONResponse(
                {"detail": "拒绝跨站请求；请从 FlowLab 页面操作"},
                status_code=403,
            )
    return await call_next(request)


def _check_pickle_token(token: str | None) -> None:
    if not token or not secrets.compare_digest(token, PICKLE_TOKEN):
        raise HTTPException(403, "加载 pickle 需要当前页面的会话令牌")


def _check_upload_size(file: UploadFile, label: str) -> None:
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            413,
            f"{label}超过上限 {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )


class DemoRequest(BaseModel):
    normal: int = Field(5000, ge=100, le=200_000)
    attack: int = Field(500, ge=10, le=50_000)
    seed: int = 42
    split: str = "temporal"
    models: list[str] = Field(default_factory=lambda: ["mlp", "iforest", "autoencoder"])
    threshold: float = 0.5
    ablate: str | None = None
    leaky: bool = False
    save: bool = True


def _validate(models: list[str]) -> None:
    unknown = [m for m in models if m not in available()]
    if unknown:
        raise HTTPException(400, f"未知模型: {unknown}，可用: {available()}")


@app.get("/api/health")
def health():
    return {"ok": True, "models": available(), "version": "0.4.0"}


@app.get("/api/models")
def models():
    from flowlab.models.registry import create
    return {"models": [{"name": n, "kind": create(n).kind} for n in available()]}


@app.get("/api/formats")
def formats():
    from flowlab.ingest import supported_formats
    return {"formats": supported_formats()}


@app.get("/api/session")
def session():
    """同源页面可读取会话令牌；跨站页面因同源策略无法读取。"""
    return JSONResponse({"pickle_token": PICKLE_TOKEN}, headers={"Cache-Control": "no-store"})


@app.post("/api/demo")
def demo(req: DemoRequest):
    _validate(req.models)
    df, meta, source = demo_frame(req.normal, req.attack, req.seed, req.leaky)
    spec = ExperimentSpec(models=req.models, split=req.split, seed=req.seed,
                          threshold=req.threshold, ablate=req.ablate)
    try:
        payload = execute(df, meta, source, spec)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if req.save:
        payload["run_id"] = save_run(payload)
    return payload


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), labels: UploadFile | None = File(None),
                 split: str = Form("temporal"), models: str = Form("mlp,iforest,autoencoder"),
                 threshold: float = Form(0.5), seed: int = Form(42),
                 ablate: str = Form(""), allow_pickle: bool = Form(False),
                 save: bool = Form(True),
                 pickle_token: str | None = Header(None, alias="X-FlowLab-Pickle-Token")):
    mlist = [m.strip() for m in models.split(",") if m.strip()]
    _validate(mlist)
    if allow_pickle:
        _check_pickle_token(pickle_token)
    _check_upload_size(file, "数据文件")

    name = file.filename or "upload"
    suffix = Path(name).suffix.lower()
    data = await file.read()
    if not data:
        raise HTTPException(400, "文件为空")

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / f"upload{suffix or '.csv'}"
        p.write_bytes(data)
        lab_path = None
        if labels is not None:
            _check_upload_size(labels, "标签文件")
            lab_data = await labels.read()
            if lab_data:
                lab_path = Path(td) / f"labels{Path(labels.filename or 'labels.csv').suffix or '.csv'}"
                lab_path.write_bytes(lab_data)
        try:
            from flowlab.ingest.pcap import PcapUnavailable
            try:
                loaded = load_frame(p, lab_path, allow_pickle=allow_pickle)
            except PcapUnavailable as exc:
                raise HTTPException(400, str(exc)) from exc
            df, meta = loaded.df, loaded.meta()
            if labels is not None and meta.get("labels", {}).get("file"):
                meta["labels"]["file"] = labels.filename
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(400, f"读取失败：{exc}") from exc

    if "label" not in df.columns:
        raise HTTPException(
            400,
            "这份数据没有标签列，无法算 AUC/F1。可以在文件里补 label 列，"
            "上传一个标签 CSV（五元组 / flow_id / 行序对齐），或改用 score 命令做无监督排序。",
        )

    spec = ExperimentSpec(models=mlist, split=split, seed=seed,
                          threshold=threshold, ablate=ablate or None)
    try:
        payload = execute(df, meta, name, spec)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if allow_pickle:
        payload["warnings"].append({
            "rule": "pickle_unsafe", "columns": [], "severity": "medium",
            "message": "该文件以 pickle 加载，反序列化会执行代码；请只加载自己生成的文件。",
            "suggestion": "分享数据时优先用 parquet / npz / csv。",
        })
    if save:
        payload["run_id"] = save_run(payload)
    return payload


@app.get("/api/history")
def history(limit: int = 20):
    return {"runs": list_runs(limit)}


@app.delete("/api/history")
def history_prune(keep: int = 50):
    from flowlab.store import count, prune
    removed = prune(keep)
    return {"deleted": removed, "remaining": count()}


@app.get("/api/history/{run_id}")
def history_item(run_id: str):
    rec = get_run(run_id)
    if rec is None:
        raise HTTPException(404, "没有这次实验")
    payload = rec["payload"]
    payload["run_id"] = rec["id"]
    return payload


@app.get("/api/history/{run_id}/report.html", response_class=HTMLResponse)
def history_html(run_id: str):
    rec = get_run(run_id)
    if rec is None:
        raise HTTPException(404, "没有这次实验")
    return rec["payload"].get("report_html", "<p>这次实验没有 HTML 报告</p>")


@app.get("/api/history/{run_id}/report.md", response_class=PlainTextResponse)
def history_md(run_id: str):
    rec = get_run(run_id)
    if rec is None:
        raise HTTPException(404, "没有这次实验")
    return rec["payload"].get("report_md", "")


_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="web")
