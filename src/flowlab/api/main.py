"""本地 API：给前端用的一个薄层，不引入数据库服务（只用一个 SQLite 文件）。

启动：uv run flowlab serve  →  http://127.0.0.1:8765
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from flowlab.eval.runner import run_experiment
from flowlab.models.registry import available
from flowlab.payload import build_payload
from flowlab.pipeline import load_frame
from flowlab.schema import normalize_columns
from flowlab.store import get_run, list_runs, save_run
from flowlab.synthetic import generate

app = FastAPI(title="FlowLab", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class DemoRequest(BaseModel):
    normal: int = Field(5000, ge=100, le=200_000)
    attack: int = Field(500, ge=10, le=50_000)
    seed: int = 42
    split: str = "temporal"
    models: list[str] = Field(default_factory=lambda: ["mlp", "iforest", "autoencoder"])
    threshold: float = 0.5
    explain: bool = True
    ablate: str | None = None
    save: bool = True


def _validate(models: list[str]) -> None:
    unknown = [m for m in models if m not in available()]
    if unknown:
        raise HTTPException(400, f"未知模型: {unknown}，可用: {available()}")


@app.get("/api/health")
def health():
    return {"ok": True, "models": available(), "version": "0.3.0"}


@app.get("/api/models")
def models():
    from flowlab.models.registry import create
    return {"models": [{"name": n, "kind": create(n).kind} for n in available()]}


@app.post("/api/demo")
def demo(req: DemoRequest):
    _validate(req.models)
    from flowlab.engineer import add_engineered_features, describe
    df = add_engineered_features(
        normalize_columns(generate(n_normal=req.normal, n_attack=req.attack, seed=req.seed)))
    meta = {"engineering": describe(),
            "labels": {"mode": "embedded", "labelled": len(df), "total": len(df)}}
    try:
        results, warns = run_experiment(df, models=req.models, split=req.split, seed=req.seed,
                                        threshold=req.threshold, explain=req.explain)
        ablation = None
        if req.ablate:
            from flowlab.eval.ablation import ablate
            ablation = ablate(df, req.ablate, models=req.models, split=req.split,
                              seed=req.seed, threshold=req.threshold).to_dict()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    payload = build_payload(df, results, warns, "合成数据", meta, ablation=ablation)
    if req.save:
        payload["run_id"] = save_run(payload)
    return payload


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), labels: UploadFile | None = File(None),
                 split: str = Form("temporal"), models: str = Form("mlp,iforest,autoencoder"),
                 threshold: float = Form(0.5), seed: int = Form(42),
                 ablate: str = Form(""), save: bool = Form(True)):
    mlist = [m.strip() for m in models.split(",") if m.strip()]
    _validate(mlist)

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
            lab_data = await labels.read()
            if lab_data:
                lab_path = Path(td) / "labels.csv"
                lab_path.write_bytes(lab_data)
        try:
            from flowlab.ingest.pcap import PcapUnavailable
            try:
                loaded = load_frame(p, lab_path)
            except PcapUnavailable as exc:
                raise HTTPException(400, str(exc)) from exc
            df, meta = loaded.df, loaded.meta()
            if labels is not None and meta.get("labels", {}).get("file"):
                meta["labels"]["file"] = labels.filename
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(400, str(exc)) from exc

    if "label" not in df.columns:
        raise HTTPException(
            400,
            "这份数据没有标签列，无法算 AUC/F1。pcap 请同时上传标签 CSV（五元组或 flow_id 对齐），"
            "或者用 CLI 的 score 子命令做无监督排序。",
        )

    try:
        results, warns = run_experiment(df, models=mlist, split=split, seed=seed,
                                        threshold=threshold, explain=True)
        ablation = None
        if ablate:
            from flowlab.eval.ablation import ablate as run_ablation
            ablation = run_ablation(df, ablate, models=mlist, split=split,
                                    seed=seed, threshold=threshold).to_dict()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    payload = build_payload(df, results, warns, name, meta, ablation=ablation)
    if save:
        payload["run_id"] = save_run(payload)
    return payload


@app.get("/api/history")
def history(limit: int = 20):
    return {"runs": list_runs(limit)}


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
