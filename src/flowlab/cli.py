"""FlowLab 命令行入口。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from flowlab.eval.runner import run_experiment
from flowlab.pipeline import load_frame
from flowlab.eval.table import as_json, markdown_table
from flowlab.features.leakage import summarize
from flowlab.report.markdown import render_report
from flowlab.schema import normalize_columns


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="flowlab", description="流量异常检测研究/实验工作台")
    sub = p.add_subparsers(dest="cmd")

    d = sub.add_parser("demo", help="用合成数据跑一次完整实验")
    d.add_argument("--normal", type=int, default=5000)
    d.add_argument("--attack", type=int, default=500)
    d.add_argument("--models", default="mlp,iforest,autoencoder")
    d.add_argument("--split", default="temporal", choices=["temporal", "random"])
    d.add_argument("--seed", type=int, default=42)
    d.add_argument("--json", action="store_true")
    d.add_argument("--report", type=Path, help="把 Markdown 报告写到该路径")

    r = sub.add_parser("run", help="对 CSV/pcap 跑实验")
    r.add_argument("file", type=Path)
    r.add_argument("--models", default="mlp,iforest,autoencoder")
    r.add_argument("--split", default="temporal", choices=["temporal", "random"])
    r.add_argument("--seed", type=int, default=42)
    r.add_argument("--json", action="store_true")
    r.add_argument("--report", type=Path)
    r.add_argument("--labels", type=Path, help="旁挂标签 CSV（pcap 没有标签时用）")

    s = sub.add_parser("score", help="对无标签数据（如 pcap）打分，输出最可疑的流")
    s.add_argument("file", type=Path)
    s.add_argument("--model", default="iforest")
    s.add_argument("--top", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--labels", type=Path, help="旁挂标签 CSV（可选，仅用于展示真实标签）")

    sv = sub.add_parser("serve", help="启动本地 Web 界面")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8765)

    sub.add_parser("models", help="列出已注册模型")
    return p


def _load(path: Path, labels: Path | None = None):
    return load_frame(path, labels)


def _emit(results, warns, args, source: str, rows: int, meta: dict | None = None) -> int:
    if args.json:
        print(as_json(results))
    else:
        print("== 数据泄漏检查 ==")
        print(summarize(warns))
        print()
        print("== 模型对比 ==")
        print(markdown_table(results))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        report_meta = {"source": source, "rows": rows, **(meta or {})}
        if results:
            report_meta["attack_support"] = results[0].metrics.get("attack_support")
        args.report.write_text(render_report(results, warns, report_meta),
                               encoding="utf-8")
        print(f"\n报告已写入 {args.report}", file=sys.stderr if args.json else sys.stdout)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd is None:
        build_parser().print_help()
        return 0

    if args.cmd == "models":
        from flowlab.models.registry import available
        print("\n".join(available()))
        return 0

    if args.cmd == "serve":
        import uvicorn
        from flowlab.api.main import app
        print(f"FlowLab 已启动: http://{args.host}:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
        return 0

    if args.cmd == "score":
        from flowlab.features.prepare import build_feature_matrix
        from flowlab.models.registry import create
        if not args.file.exists():
            print(f"文件不存在: {args.file}", file=sys.stderr)
            return 2
        loaded = _load(args.file, getattr(args, "labels", None))
        df = loaded.df
        X, feats = build_feature_matrix(df)
        det = create(args.model)
        det.fit(X, None)
        scores = det.score(X)
        view = df.copy()
        view["score"] = scores
        show = [c for c in ("src_ip", "dst_ip", "dst_port", "protocol", "timestamp",
                            "bytes_per_s", "packets_per_s") if c in view.columns]
        top = view.sort_values("score", ascending=False).head(args.top)
        if args.json:
            import json
            print(json.dumps(top[show + ["score"]].round(4).to_dict("records"), ensure_ascii=False, indent=2))
        else:
            print(f"== Top {len(top)} 可疑流（模型 {args.model}，共 {len(view)} 条）==")
            if loaded.label_info:
                print(f"   标签对齐: {loaded.label_info}")
            print(top[show + ["score"]].round(4).to_string(index=False))
        return 0

    if args.cmd == "demo":
        from flowlab.synthetic import generate
        from flowlab.engineer import add_engineered_features, describe
        df = add_engineered_features(
            normalize_columns(generate(n_normal=args.normal, n_attack=args.attack, seed=args.seed)))
        source = "合成数据（synthetic.py）"
        meta = {"engineering": describe(), "labels": {"mode": "embedded"}}
    else:
        if not args.file.exists():
            print(f"文件不存在: {args.file}", file=sys.stderr)
            return 2
        loaded = _load(args.file, getattr(args, "labels", None))
        df, source, meta = loaded.df, loaded.source, loaded.meta()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    results, warns = run_experiment(df, models=models, split=args.split, seed=args.seed)
    return _emit(results, warns, args, source, len(df), meta)
