"""本地 API：薄层，编排全在 service.execute()。

启动：uv run flowlab serve  →  http://127.0.0.1:8765
"""

from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from flowlab import __version__
from flowlab.models.registry import available
from flowlab.pipeline import load_frame
from flowlab.service import ExperimentSpec, demo_frame, execute
from flowlab.store import get_run, list_runs, save_run

app = FastAPI(title="FlowLab", version=__version__)

PICKLE_TOKEN = secrets.token_urlsafe(32)
MAX_UPLOAD_BYTES = int(os.getenv("FLOWLAB_MAX_UPLOAD_MB", "1024")) * 1024 * 1024
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _origin_parts(value: str) -> tuple[str, str, int] | None:
    """把 Origin/URL 归一成 (scheme, host, port)，默认端口也不放过。"""
    try:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        default_port = 443 if parsed.scheme == "https" else 80
        return parsed.scheme, parsed.hostname.lower(), parsed.port or default_port
    except ValueError:
        return None


def _same_origin(origin: str, request: Request) -> bool:
    """严格比较 scheme + host + port；需要额外来源时用环境变量显式放行。"""
    candidate = _origin_parts(origin)
    expected = _origin_parts(str(request.base_url))
    if candidate is None or expected is None:
        return False
    if candidate == expected:
        return True
    allowed = {
        parts
        for value in os.getenv("FLOWLAB_ALLOWED_ORIGINS", "").split(",")
        if value.strip()
        for parts in [_origin_parts(value.strip())]
        if parts is not None
    }
    return candidate in allowed


def _content_length(request: Request) -> int | None:
    raw = request.headers.get("content-length")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


@app.middleware("http")
async def reject_cross_site_writes(request: Request, call_next):
    """阻止网页跨站触发写操作；无 Origin 的 CLI/curl 调用不受影响。"""
    if request.method in MUTATING_METHODS and request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site" or (
            origin and not _same_origin(origin, request)
        ):
            return JSONResponse(
                {"detail": "拒绝跨站请求；请从 FlowLab 页面操作"},
                status_code=403,
            )
    if request.url.path == "/api/upload":
        # multipart 有两份可选文件（数据 + 标签），给协议开销留 1 MB 余量。
        max_body = MAX_UPLOAD_BYTES * 2 + 1024 * 1024
        declared = _content_length(request)
        if declared is not None and declared > max_body:
            return JSONResponse(
                {"detail": f"上传请求超过上限 {max_body // (1024 * 1024)} MB"},
                status_code=413,
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


async def _save_upload(file: UploadFile, path: Path, label: str) -> int:
    """分块写入临时文件，边写边校验，不把整个上传读进额外内存。"""
    total = 0
    with path.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    413,
                    f"{label}超过上限 {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
                )
            out.write(chunk)
    return total


class DemoRequest(BaseModel):
    normal: int = Field(5000, ge=100, le=200_000)
    attack: int = Field(500, ge=10, le=50_000)
    seed: int = Field(42, ge=0, le=2**32 - 1)
    split: Literal["temporal", "random"] = "temporal"
    test_size: float = Field(0.3, ge=0.05, le=0.5)
    models: list[str] = Field(
        default_factory=lambda: ["mlp", "iforest", "autoencoder"], min_length=1
    )
    threshold: float = Field(0.5, ge=0, le=1)
    ablate: str | None = None
    leaky: bool = False
    save: bool = True


def _validate(models: list[str]) -> None:
    if not models:
        raise HTTPException(400, "至少选择一个模型")
    unknown = [m for m in models if m not in available()]
    if unknown:
        raise HTTPException(400, f"未知模型: {unknown}，可用: {available()}")


@app.get("/api/health")
def health():
    return {"ok": True, "models": available(), "version": __version__}


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
    spec = ExperimentSpec(
        models=req.models,
        split=req.split,
        seed=req.seed,
        threshold=req.threshold,
        test_size=req.test_size,
        ablate=req.ablate,
        source_kind="demo",
        normal=req.normal,
        attack=req.attack,
        leaky=req.leaky,
    )
    try:
        payload = execute(df, meta, source, spec)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if req.save:
        payload["run_id"] = save_run(payload)
    return payload


@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    labels: UploadFile | None = File(None),
    split: str = Form("temporal"),
    models: str = Form("mlp,iforest,autoencoder"),
    threshold: float = Form(0.5),
    seed: int = Form(42),
    test_size: float = Form(0.3),
    ablate: str = Form(""),
    allow_pickle: bool = Form(False),
    save: bool = Form(True),
    pickle_token: str | None = Header(None, alias="X-FlowLab-Pickle-Token"),
):
    mlist = [m.strip() for m in models.split(",") if m.strip()]
    _validate(mlist)
    if split not in {"temporal", "random"}:
        raise HTTPException(400, "split 只能是 temporal 或 random")
    if not 0 <= threshold <= 1:
        raise HTTPException(400, "threshold 应在 0~1 之间")
    if not 0.05 <= test_size <= 0.5:
        raise HTTPException(400, "test_size 应在 0.05~0.5 之间")
    if not 0 <= seed <= 2**32 - 1:
        raise HTTPException(400, "seed 超出允许范围")
    if allow_pickle:
        _check_pickle_token(pickle_token)
    _check_upload_size(file, "数据文件")

    name = file.filename or "upload"
    safe_name = Path(name).name or "upload.csv"
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / f"data-{safe_name}"
        if await _save_upload(file, p, "数据文件") == 0:
            raise HTTPException(400, "文件为空")
        lab_path = None
        if labels is not None:
            _check_upload_size(labels, "标签文件")
            label_name = Path(labels.filename or "labels.csv").name or "labels.csv"
            candidate = Path(td) / f"labels-{label_name}"
            if await _save_upload(labels, candidate, "标签文件"):
                lab_path = candidate
        try:
            from flowlab.ingest.pcap import PcapUnavailable

            try:
                loaded = await run_in_threadpool(load_frame, p, lab_path, allow_pickle=allow_pickle)
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

    spec = ExperimentSpec(
        models=mlist,
        split=split,
        seed=seed,
        threshold=threshold,
        test_size=test_size,
        ablate=ablate or None,
        source_kind="upload",
        source_ref=name,
    )
    try:
        payload = await run_in_threadpool(execute, df, meta, name, spec)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if allow_pickle:
        payload["warnings"].append(
            {
                "rule": "pickle_unsafe",
                "columns": [],
                "severity": "medium",
                "message": "该文件以 pickle 加载，反序列化会执行代码；请只加载自己生成的文件。",
                "suggestion": "分享数据时优先用 parquet / npz / csv。",
            }
        )
    if save:
        payload["run_id"] = save_run(payload)
    return payload


@app.get("/api/history")
def history(limit: int = Query(20, ge=1, le=100)):
    return {"runs": list_runs(limit)}


@app.delete("/api/history")
def history_prune(keep: int = Query(50, ge=1, le=5000)):
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


_PACKAGED_DIST = Path(__file__).resolve().parent.parent / "web"
_REPO_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"
_DIST = _PACKAGED_DIST if _PACKAGED_DIST.exists() else _REPO_DIST
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="web")
