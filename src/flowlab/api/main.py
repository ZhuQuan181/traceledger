"""本地 API：给前端用的一个薄层，不引入数据库。

启动：uv run flowlab serve  →  http://127.0.0.1:8765
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from flowlab.eval.runner import run_experiment
from flowlab.models.registry import available
from flowlab.report.markdown import render_report
from flowlab.schema import normalize_columns
from flowlab.synthetic import generate

app = FastAPI(title="FlowLab", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BENIGN = "benign"


class DemoRequest(BaseModel):
    normal: int = Field(5000, ge=100, le=200_000)
    attack: int = Field(500, ge=10, le=50_000)
    seed: int = 42
    split: str = "temporal"
    models: list[str] = Field(default_factory=lambda: ["mlp", "iforest", "autoencoder"])
    threshold: float = 0.5
    explain: bool = True


def _payload(df, results, warns, source: str) -> dict:
    best = max(results, key=lambda r: (r.metrics.get("auc") or 0)) if results else None
    r0 = results[0] if results else None
    return {
        "dataset": {
            "source": source,
            "rows": int(len(df)),
            "train": r0.n_train if r0 else 0,
            "test": r0.n_test if r0 else 0,
            "hash": r0.dataset_hash if r0 else "",
            "split": r0.split if r0 else "",
            "threshold": r0.threshold if r0 else 0.5,
        },
        "warnings": warns,
        "results": [r.to_dict() for r in results],
        "best_model": best.model if best else None,
        "top_flows": best.top_flows if best else [],
        "report_md": render_report(results, warns, {"source": source, "rows": len(df)}),
    }


@app.get("/api/health")
def health():
    return {"ok": True, "models": available()}


@app.get("/api/models")
def models():
    from flowlab.models.registry import create
    return {"models": [{"name": n, "kind": create(n).kind} for n in available()]}


@app.post("/api/demo")
def demo(req: DemoRequest):
    unknown = [m for m in req.models if m not in available()]
    if unknown:
        raise HTTPException(400, f"未知模型: {unknown}")
    df = normalize_columns(generate(n_normal=req.normal, n_attack=req.attack, seed=req.seed))
    try:
        results, warns = run_experiment(df, models=req.models, split=req.split,
                                        seed=req.seed, threshold=req.threshold,
                                        explain=req.explain)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _payload(df, results, warns, "合成数据")


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), split: str = Form("temporal"),
                 models: str = Form("mlp,iforest,autoencoder"), threshold: float = Form(0.5),
                 seed: int = Form(42)):
    name = file.filename or "upload"
    suffix = Path(name).suffix.lower()
    data = await file.read()
    if not data:
        raise HTTPException(400, "文件为空")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / f"upload{suffix or '.csv'}"
        p.write_bytes(data)
        try:
            if suffix in {".pcap", ".pcapng"}:
                from flowlab.ingest.pcap import PcapUnavailable, read_pcap
                try:
                    df = read_pcap(p)
                except PcapUnavailable as exc:
                    raise HTTPException(400, str(exc)) from exc
                if "label" not in df.columns:
                    raise HTTPException(
                        400,
                        "pcap 没有标签列，无法做监督评估。请在 CSV 里补 label 列，"
                        "或使用 CLI 的 score 子命令做无监督排序。",
                    )
            else:
                from flowlab.ingest.csv import read_csv
                df = read_csv(p)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(400, str(exc)) from exc

    mlist = [m.strip() for m in models.split(",") if m.strip()]
    try:
        results, warns = run_experiment(df, models=mlist, split=split, seed=seed,
                                        threshold=threshold, explain=True)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _payload(df, results, warns, name)


@app.post("/api/report", response_class=PlainTextResponse)
def report(payload: dict):
    """把前端手里的结果渲染成 Markdown（无需重跑）。"""
    from flowlab.eval.runner import EvalResult
    try:
        results = [EvalResult(**{k: v for k, v in r.items() if k in EvalResult.__dataclass_fields__})
                   for r in payload.get("results", [])]
    except TypeError as exc:
        raise HTTPException(400, f"结果格式不正确: {exc}") from exc
    return render_report(results, payload.get("warnings", []), payload.get("dataset", {}))


_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="web")
