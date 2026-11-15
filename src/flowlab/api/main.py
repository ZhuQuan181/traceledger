"""本地 API：薄层，编排全在 service.execute()。

启动：uv run flowlab serve  →  http://127.0.0.1:8765
"""

from __future__ import annotations

import os
import secrets
import shutil
import tempfile
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.middleware.gzip import GZipMiddleware

from flowlab import __version__
from flowlab.compare import load_comparison
from flowlab.jobs import JOBS, JobNotCancellable, JobQueueFull
from flowlab.models.registry import available
from flowlab.pipeline import load_frame
from flowlab.preflight import preflight_frame
from flowlab.service import ExperimentSpec, demo_frame, execute, score_payload
from flowlab.store import (
    delete_run,
    get_run,
    history_page,
    save_run,
    update_run,
)

app = FastAPI(title="FlowLab", version=__version__)
app.add_middleware(GZipMiddleware, minimum_size=1024)

PICKLE_TOKEN = secrets.token_urlsafe(32)
MAX_UPLOAD_BYTES = int(os.getenv("FLOWLAB_MAX_UPLOAD_MB", "1024")) * 1024 * 1024
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "font-src 'self' data:; img-src 'self' data:; connect-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def _host_name(value: str) -> str | None:
    """从 Host/Origin 风格的值里取出小写主机名，兼容 IPv6 与端口。"""
    try:
        host = urlparse(f"//{value}").hostname
    except ValueError:
        return None
    return host.lower() if host else None


def _allowed_hosts() -> set[str]:
    configured = {
        host.strip().lower()
        for host in os.getenv("FLOWLAB_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    }
    return LOOPBACK_HOSTS | configured


def _is_allowed_host(value: str | None) -> bool:
    if not value:
        return False
    return _host_name(value) in _allowed_hosts()


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


def _with_security_headers(response):
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


@app.middleware("http")
async def guard_local_api(request: Request, call_next):
    """校验 Host 并阻止跨站写操作。

    Origin 检查不能只依赖 ``request.base_url``：该值来自可伪造的 Host 头。
    先固定 Host 白名单，才能阻断 DNS rebinding 把恶意域名解析到 localhost。
    """
    if not _is_allowed_host(request.headers.get("host")):
        return _with_security_headers(
            JSONResponse(
                {
                    "detail": (
                        "拒绝不受信任的 Host。默认只允许 localhost / 127.0.0.1 / ::1；"
                        "远程访问请设置 FLOWLAB_ALLOWED_HOSTS。"
                    )
                },
                status_code=403,
            )
        )
    if request.method in MUTATING_METHODS and request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site" or (
            origin and not _same_origin(origin, request)
        ):
            return _with_security_headers(
                JSONResponse(
                    {"detail": "拒绝跨站请求；请从 FlowLab 页面操作"},
                    status_code=403,
                )
            )
    if request.url.path in {
        "/api/upload",
        "/api/jobs/upload",
        "/api/jobs/score",
        "/api/preflight",
    }:
        # multipart 有两份可选文件（数据 + 标签），给协议开销留 1 MB 余量。
        max_body = MAX_UPLOAD_BYTES * 2 + 1024 * 1024
        declared = _content_length(request)
        if declared is not None and declared > max_body:
            return _with_security_headers(
                JSONResponse(
                    {"detail": f"上传请求超过上限 {max_body // (1024 * 1024)} MB"},
                    status_code=413,
                )
            )
    return _with_security_headers(await call_next(request))


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


async def _stage_job_files(
    file: UploadFile,
    labels: UploadFile | None,
    workdir: Path,
) -> tuple[Path, Path | None, str, str | None]:
    """把 multipart 文件复制进任务专属目录，后台线程不再依赖请求作用域。"""
    name = file.filename or "upload"
    label_original = labels.filename if labels is not None else None
    safe_name = Path(name).name or "upload.csv"
    data_path = workdir / f"data-{safe_name}"
    if await _save_upload(file, data_path, "数据文件") == 0:
        raise HTTPException(400, "文件为空")
    label_path = None
    if labels is not None:
        _check_upload_size(labels, "标签文件")
        label_name = Path(labels.filename or "labels.csv").name or "labels.csv"
        candidate = workdir / f"labels-{label_name}"
        if await _save_upload(labels, candidate, "标签文件"):
            label_path = candidate
    return data_path, label_path, name, label_original


class DemoRequest(BaseModel):
    normal: int = Field(5000, ge=100, le=200_000)
    attack: int = Field(500, ge=10, le=50_000)
    seed: int = Field(42, ge=0, le=2**32 - 1)
    split: Literal["temporal", "random", "group"] = "temporal"
    test_size: float = Field(0.3, ge=0.05, le=0.5)
    validation_size: float = Field(0.2, ge=0.05, le=0.4)
    models: list[str] = Field(
        default_factory=lambda: ["mlp", "iforest", "autoencoder"], min_length=1
    )
    threshold: float = Field(0.5, ge=0, le=1)
    target_fpr: float = Field(0.01, gt=0, lt=1)
    threshold_mode: Literal["fixed", "f1", "fpr"] = "fixed"
    ablate: str | None = None
    leaky: bool = False
    save: bool = True


class JobDemoRequest(DemoRequest):
    """后台任务只接受可保存的请求，前端用 run_id 获取完整结果。"""

    save: Literal[True] = True


class HistoryUpdate(BaseModel):
    note: str | None = Field(None, max_length=500)
    status: Literal["unreviewed", "baseline", "failed", "archived"] | None = None


def _validate(models: list[str]) -> None:
    if not models:
        raise HTTPException(400, "至少选择一个模型")
    unknown = [m for m in models if m not in available()]
    if unknown:
        raise HTTPException(400, f"未知模型: {unknown}，可用: {available()}")


def _validate_score_model(model: str) -> None:
    from flowlab.models.registry import create

    if model not in available():
        raise HTTPException(400, f"未知模型: {model}，可用: {available()}")
    if create(model).kind != "unsupervised":
        raise HTTPException(400, "无标签打分只能使用无监督模型（iforest / autoencoder）")


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
        threshold_mode=req.threshold_mode,
        target_fpr=req.target_fpr,
        test_size=req.test_size,
        validation_size=req.validation_size,
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


@app.post("/api/jobs/demo", status_code=202)
def demo_job(req: JobDemoRequest):
    _validate(req.models)

    def runner(progress, cancel):
        progress("loading", 0, 1)
        df, meta, source = demo_frame(req.normal, req.attack, req.seed, req.leaky)
        progress("loading", 1, 1)
        spec = ExperimentSpec(
            models=req.models,
            split=req.split,
            seed=req.seed,
            threshold=req.threshold,
            threshold_mode=req.threshold_mode,
            target_fpr=req.target_fpr,
            test_size=req.test_size,
            validation_size=req.validation_size,
            ablate=req.ablate,
            source_kind="demo",
            normal=req.normal,
            attack=req.attack,
            leaky=req.leaky,
        )
        return execute(df, meta, source, spec, progress=progress, cancel=cancel)

    try:
        return JOBS.submit(
            "demo",
            model_count=len(set(req.models)),
            has_ablation=bool(req.ablate),
            save=True,
            runner=runner,
        )
    except JobQueueFull as exc:
        raise HTTPException(429, str(exc)) from exc


@app.get("/api/jobs/active")
def active_jobs():
    return {"jobs": JOBS.active()}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "没有这个后台任务，记录可能已过期或被清理")
    return job


@app.delete("/api/jobs/{job_id}")
def job_cancel(job_id: str):
    try:
        return JOBS.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(404, "没有这个后台任务") from exc
    except JobNotCancellable as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/jobs/{job_id}/result")
def job_result(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "没有这个后台任务")
    if job["status"] != "succeeded":
        raise HTTPException(409, f"任务尚未成功完成（当前状态：{job['status']}）")
    result = JOBS.result(job_id)
    if result is None:
        raise HTTPException(404, "结果已写入历史库，请通过 run_id 读取")
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@app.post("/api/preflight")
async def preflight(
    file: UploadFile = File(...),
    labels: UploadFile | None = File(None),
    split: str = Form("temporal"),
    test_size: float = Form(0.3),
    validation_size: float = Form(0.2),
    seed: int = Form(42),
    allow_pickle: bool = Form(False),
    pickle_token: str | None = Header(None, alias="X-FlowLab-Pickle-Token"),
):
    if split not in {"temporal", "random", "group"}:
        raise HTTPException(400, "split 只能是 temporal、random 或 group")
    if not 0.05 <= test_size <= 0.5:
        raise HTTPException(400, "test_size 应在 0.05~0.5 之间")
    if not 0.05 <= validation_size <= 0.4:
        raise HTTPException(400, "validation_size 应在 0.05~0.4 之间")
    if test_size + validation_size > 0.8:
        raise HTTPException(400, "test_size + validation_size 不能超过 0.8")
    if not 0 <= seed <= 2**32 - 1:
        raise HTTPException(400, "seed 超出允许范围")
    if allow_pickle:
        _check_pickle_token(pickle_token)
    _check_upload_size(file, "数据文件")

    with tempfile.TemporaryDirectory(prefix="flowlab-preflight-") as td:
        data_path, label_path, name, _ = await _stage_job_files(file, labels, Path(td))
        try:
            from flowlab.ingest.pcap import PcapUnavailable

            loaded = await run_in_threadpool(
                load_frame, data_path, label_path, allow_pickle=allow_pickle
            )
            report = await run_in_threadpool(
                preflight_frame,
                loaded.df,
                source=name,
                raw_columns=loaded.raw_columns,
                split=split,
                test_size=test_size,
                validation_size=validation_size,
                seed=seed,
            )
        except PcapUnavailable as exc:
            raise HTTPException(400, str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(400, f"预检失败：{exc}") from exc
    return JSONResponse(report, headers={"Cache-Control": "no-store"})


@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    labels: UploadFile | None = File(None),
    split: str = Form("temporal"),
    models: str = Form("mlp,iforest,autoencoder"),
    threshold: float = Form(0.5),
    threshold_mode: str = Form("fixed"),
    target_fpr: float = Form(0.01),
    seed: int = Form(42),
    test_size: float = Form(0.3),
    validation_size: float = Form(0.2),
    ablate: str = Form(""),
    allow_pickle: bool = Form(False),
    save: bool = Form(True),
    pickle_token: str | None = Header(None, alias="X-FlowLab-Pickle-Token"),
):
    mlist = [m.strip() for m in models.split(",") if m.strip()]
    _validate(mlist)
    if split not in {"temporal", "random", "group"}:
        raise HTTPException(400, "split 只能是 temporal、random 或 group")
    if not 0 <= threshold <= 1:
        raise HTTPException(400, "threshold 应在 0~1 之间")
    if threshold_mode not in {"fixed", "f1", "fpr"}:
        raise HTTPException(400, "threshold_mode 只能是 fixed、f1 或 fpr")
    if not 0 < target_fpr < 1:
        raise HTTPException(400, "target_fpr 应在 0~1 之间")
    if not 0.05 <= test_size <= 0.5:
        raise HTTPException(400, "test_size 应在 0.05~0.5 之间")
    if not 0.05 <= validation_size <= 0.4:
        raise HTTPException(400, "validation_size 应在 0.05~0.4 之间")
    if test_size + validation_size > 0.8:
        raise HTTPException(400, "test_size + validation_size 不能超过 0.8")
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
        threshold_mode=threshold_mode,
        target_fpr=target_fpr,
        test_size=test_size,
        validation_size=validation_size,
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


@app.post("/api/jobs/upload", status_code=202)
async def upload_job(
    file: UploadFile = File(...),
    labels: UploadFile | None = File(None),
    split: str = Form("temporal"),
    models: str = Form("mlp,iforest,autoencoder"),
    threshold: float = Form(0.5),
    threshold_mode: str = Form("fixed"),
    target_fpr: float = Form(0.01),
    seed: int = Form(42),
    test_size: float = Form(0.3),
    validation_size: float = Form(0.2),
    ablate: str = Form(""),
    allow_pickle: bool = Form(False),
    pickle_token: str | None = Header(None, alias="X-FlowLab-Pickle-Token"),
):
    mlist = list(dict.fromkeys(m.strip() for m in models.split(",") if m.strip()))
    _validate(mlist)
    if split not in {"temporal", "random", "group"}:
        raise HTTPException(400, "split 只能是 temporal、random 或 group")
    if not 0 <= threshold <= 1:
        raise HTTPException(400, "threshold 应在 0~1 之间")
    if threshold_mode not in {"fixed", "f1", "fpr"}:
        raise HTTPException(400, "threshold_mode 只能是 fixed、f1 或 fpr")
    if not 0 < target_fpr < 1:
        raise HTTPException(400, "target_fpr 应在 0~1 之间")
    if not 0.05 <= test_size <= 0.5:
        raise HTTPException(400, "test_size 应在 0.05~0.5 之间")
    if not 0.05 <= validation_size <= 0.4:
        raise HTTPException(400, "validation_size 应在 0.05~0.4 之间")
    if test_size + validation_size > 0.8:
        raise HTTPException(400, "test_size + validation_size 不能超过 0.8")
    if not 0 <= seed <= 2**32 - 1:
        raise HTTPException(400, "seed 超出允许范围")
    if allow_pickle:
        _check_pickle_token(pickle_token)
    _check_upload_size(file, "数据文件")
    if not JOBS.can_accept():
        raise HTTPException(429, "本机已有一个实验在运行、另一个在排队；请等待或先取消排队任务。")

    workdir = JOBS.make_workdir()
    try:
        data_path, label_path, name, label_original = await _stage_job_files(file, labels, workdir)

        def runner(progress, cancel):
            from flowlab.ingest.pcap import PcapUnavailable

            progress("loading", 0, 1)
            try:
                loaded = load_frame(
                    data_path,
                    label_path,
                    allow_pickle=allow_pickle,
                )
            except PcapUnavailable as exc:
                raise ValueError(str(exc)) from exc
            except Exception as exc:  # noqa: BLE001 - 后台任务边界统一转成用户提示
                raise ValueError(f"读取失败：{exc}") from exc
            progress("loading", 1, 1)
            meta = loaded.meta()
            if label_original and meta.get("labels", {}).get("file"):
                meta["labels"]["file"] = label_original
            spec = ExperimentSpec(
                models=mlist,
                split=split,
                seed=seed,
                threshold=threshold,
                threshold_mode=threshold_mode,
                target_fpr=target_fpr,
                test_size=test_size,
                validation_size=validation_size,
                ablate=ablate or None,
                source_kind="upload",
                source_ref=name,
            )
            payload = execute(
                loaded.df,
                meta,
                name,
                spec,
                progress=progress,
                cancel=cancel,
            )
            if allow_pickle:
                payload["warnings"].append(
                    {
                        "rule": "pickle_unsafe",
                        "columns": [],
                        "severity": "medium",
                        "message": (
                            "该文件以 pickle 加载，反序列化会执行代码；请只加载自己生成的文件。"
                        ),
                        "suggestion": "分享数据时优先用 parquet / npz / csv。",
                    }
                )
            return payload

        try:
            return JOBS.submit(
                "upload",
                model_count=len(mlist),
                has_ablation=bool(ablate),
                save=True,
                runner=runner,
                workdir=workdir,
            )
        except JobQueueFull as exc:
            raise HTTPException(429, str(exc)) from exc
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise


@app.post("/api/jobs/score", status_code=202)
async def score_job(
    file: UploadFile = File(...),
    model: str = Form("iforest"),
    top: int = Form(50),
    allow_pickle: bool = Form(False),
    pickle_token: str | None = Header(None, alias="X-FlowLab-Pickle-Token"),
):
    _validate_score_model(model)
    if not 1 <= top <= 500:
        raise HTTPException(400, "top 应在 1~500 之间")
    if allow_pickle:
        _check_pickle_token(pickle_token)
    _check_upload_size(file, "数据文件")
    if not JOBS.can_accept():
        raise HTTPException(429, "本机已有一个实验在运行、另一个在排队；请等待或先取消排队任务。")

    workdir = JOBS.make_workdir()
    try:
        data_path, _, name, _ = await _stage_job_files(file, None, workdir)

        def runner(progress, cancel):
            from flowlab.ingest.pcap import PcapUnavailable

            progress("loading", 0, 1)
            try:
                loaded = load_frame(data_path, None, allow_pickle=allow_pickle)
            except PcapUnavailable as exc:
                raise ValueError(str(exc)) from exc
            except Exception as exc:  # noqa: BLE001 - 后台任务边界统一转成用户提示
                raise ValueError(f"读取失败：{exc}") from exc
            progress("loading", 1, 1)
            payload = score_payload(
                loaded.df,
                loaded.meta(),
                name,
                model=model,
                top=top,
                progress=progress,
                cancel=cancel,
            )
            if allow_pickle:
                payload["warnings"] = [
                    {
                        "rule": "pickle_unsafe",
                        "severity": "medium",
                        "message": (
                            "该文件以 pickle 加载，反序列化会执行代码；请只加载自己生成的文件。"
                        ),
                    }
                ]
            else:
                payload["warnings"] = []
            return payload

        try:
            return JOBS.submit(
                "score",
                model_count=1,
                has_ablation=False,
                save=False,
                runner=runner,
                workdir=workdir,
            )
        except JobQueueFull as exc:
            raise HTTPException(429, str(exc)) from exc
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise


@app.get("/api/history")
def history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str = Query("", max_length=200),
    model: str | None = Query(None, max_length=80),
    status: Literal["unreviewed", "baseline", "failed", "archived"] | None = None,
):
    return history_page(limit, offset, q, model, status)


@app.patch("/api/history/{run_id}")
def history_update(run_id: str, req: HistoryUpdate):
    if req.note is None and req.status is None:
        raise HTTPException(400, "至少提供 note 或 status")
    try:
        record = update_run(run_id, note=req.note, status=req.status)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if record is None:
        raise HTTPException(404, "没有这次实验")
    return {
        "id": record["id"],
        "note": record["note"],
        "status": record["status"],
        "updated_at": record["updated_at"],
    }


@app.get("/api/compare")
def history_compare(ids: str = Query(..., description="逗号分隔的 2–4 个实验 ID")):
    run_ids = [value.strip() for value in ids.split(",") if value.strip()]
    try:
        return load_comparison(run_ids)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


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


@app.delete("/api/history/{run_id}")
def history_delete(run_id: str):
    if not delete_run(run_id):
        raise HTTPException(404, "没有这次实验")
    return {"deleted": run_id}


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
