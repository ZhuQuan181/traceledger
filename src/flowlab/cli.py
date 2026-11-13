"""FlowLab 命令行入口。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from flowlab.eval.runner import run_experiment
from flowlab.eval.table import markdown_table
from flowlab.features.leakage import summarize
from flowlab.pipeline import load_frame
from flowlab.schema import normalize_columns


def _add_run_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--models", default="mlp,iforest,autoencoder")
    p.add_argument("--split", default="temporal", choices=["temporal", "random"])
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--json", action="store_true")
    p.add_argument("--report", type=Path, help="Markdown 报告输出路径")
    p.add_argument("--html", type=Path, help="单文件 HTML 报告输出路径")
    p.add_argument("--ablate", metavar="COLUMN", help="去掉该列重跑，报出指标变化（如 dst_port）")
    p.add_argument("--no-save", action="store_true", help="不写入本地实验历史")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="flowlab", description="流量异常检测研究/实验工作台")
    sub = p.add_subparsers(dest="cmd")

    d = sub.add_parser("demo", help="用合成数据跑一次完整实验")
    d.add_argument("--normal", type=int, default=5000)
    d.add_argument("--attack", type=int, default=500)
    d.add_argument("--leaky", action="store_true",
                   help="生成只有端口不同的极端数据，用来演示端口泄漏的影响")
    _add_run_flags(d)

    r = sub.add_parser("run", help="对 CSV/pcap 跑实验")
    r.add_argument("file", type=Path)
    r.add_argument("--labels", type=Path, help="旁挂标签 CSV（pcap 没有标签时用）")
    _add_run_flags(r)

    s = sub.add_parser("score", help="对无标签数据（如 pcap）打分，输出最可疑的流")
    s.add_argument("file", type=Path)
    s.add_argument("--model", default="iforest")
    s.add_argument("--top", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--labels", type=Path, help="旁挂标签 CSV（可选，仅用于展示真实标签）")

    sv = sub.add_parser("serve", help="启动本地 Web 界面")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8765)

    h = sub.add_parser("history", help="最近的实验（本地 SQLite）")
    h.add_argument("--limit", type=int, default=20)

    sh = sub.add_parser("show", help="查看某次实验，可导出报告")
    sh.add_argument("run_id")
    sh.add_argument("--html", type=Path)
    sh.add_argument("--md", type=Path)

    cm = sub.add_parser("compare", help="对比多次实验的最佳指标")
    cm.add_argument("run_ids", nargs="+")

    sub.add_parser("models", help="列出已注册模型")
    return p


def _load(path: Path, labels: Path | None = None):
    return load_frame(path, labels)


def _print_summary(results, warns, ablation) -> None:
    print("== 数据泄漏检查 ==")
    print(summarize(warns))
    print()
    print("== 模型对比 ==")
    print(markdown_table(results))
    if ablation:
        from flowlab.eval.ablation import format_table
        print()
        print(format_table(ablation))


def _finish(payload, args) -> int:
    results = payload["results"]
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_summary(_ResultsShim(results), payload["warnings"], payload.get("ablation"))

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload["report_md"], encoding="utf-8")
        print(f"Markdown 报告：{args.report}", file=sys.stderr if args.json else sys.stdout)
    if getattr(args, "html", None):
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(payload["report_html"], encoding="utf-8")
        print(f"HTML 报告：{args.html}", file=sys.stderr if args.json else sys.stdout)

    if not getattr(args, "no_save", False):
        from flowlab.store import save_run
        rid = save_run(payload)
        print(f"实验已记录：{rid}（flowlab show {rid}）", file=sys.stderr if args.json else sys.stdout)
    return 0


class _ResultsShim(list):
    """让 markdown_table 接受 dict 形态的结果。"""

    def __iter__(self):
        from flowlab.eval.runner import EvalResult
        for r in list.__iter__(self):
            yield r if isinstance(r, EvalResult) else EvalResult(**{
                k: v for k, v in r.items() if k in EvalResult.__dataclass_fields__
            })


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

    if args.cmd == "history":
        from flowlab.store import list_runs
        runs = list_runs(args.limit)
        if not runs:
            print("还没有实验记录。跑一次 `flowlab demo`。")
            return 0
        print(f"{'ID':<12} {'时间':<20} {'数据':<28} {'最佳模型':<12} {'AUC':>7}")
        for r in runs:
            auc = "—" if r["best_auc"] is None else f"{r['best_auc']:.4f}"
            print(f"{r['id']:<12} {(r['created_at'] or '')[:19]:<20} "
                  f"{(r['source'] or '')[:26]:<28} {(r['best_model'] or '—'):<12} {auc:>7}")
        return 0

    if args.cmd == "show":
        from flowlab.store import get_run
        rec = get_run(args.run_id)
        if rec is None:
            print(f"没有这个实验：{args.run_id}", file=sys.stderr)
            return 2
        payload = rec["payload"]
        print(f"实验 {rec['id']} · {rec['created_at']} · {rec['source']}")
        print(f"数据指纹 {rec['dataset_hash']} · 切分 {rec['split']} · 阈值 {rec['threshold']}")
        print(markdown_table(_ResultsShim(payload["results"])))
        if args.md:
            args.md.parent.mkdir(parents=True, exist_ok=True)
            args.md.write_text(payload["report_md"], encoding="utf-8")
            print(f"Markdown 报告：{args.md}")
        if args.html:
            args.html.parent.mkdir(parents=True, exist_ok=True)
            args.html.write_text(payload["report_html"], encoding="utf-8")
            print(f"HTML 报告：{args.html}")
        return 0

    if args.cmd == "compare":
        from flowlab.store import compare as load_runs
        runs = load_runs(args.run_ids)
        if not runs:
            print("没有找到这些实验", file=sys.stderr)
            return 2
        base = runs[0]
        print(f"{'ID':<12} {'数据':<24} {'模型':<12} {'AUC':>8} {'相对首个':>10}")
        for rec in runs:
            auc = rec["best_auc"]
            delta = "" if (auc is None or base["best_auc"] is None) else f"{auc - base['best_auc']:+.4f}"
            print(f"{rec['id']:<12} {(rec['source'] or '')[:22]:<24} {(rec['best_model'] or '—'):<12} "
                  f"{('—' if auc is None else f'{auc:.4f}'):>8} {delta:>10}")
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
            print(json.dumps(top[show + ["score"]].round(4).to_dict("records"),
                             ensure_ascii=False, indent=2))
        else:
            print(f"== Top {len(top)} 可疑流（模型 {args.model}，共 {len(view)} 条）==")
            if loaded.label_info:
                print(f"   标签对齐: {loaded.label_info}")
            print(top[show + ["score"]].round(4).to_string(index=False))
        return 0

    # demo / run
    if args.cmd == "demo":
        from flowlab.engineer import add_engineered_features, describe
        from flowlab.synthetic import generate
        df = add_engineered_features(
            normalize_columns(generate(n_normal=args.normal, n_attack=args.attack,
                                       seed=args.seed, leakage_only=args.leaky)))
        source = "合成数据（synthetic.py）"
        meta = {"engineering": describe(), "labels": {"mode": "embedded", "labelled": args.normal + args.attack}}
    else:
        if not args.file.exists():
            print(f"文件不存在: {args.file}", file=sys.stderr)
            return 2
        loaded = _load(args.file, getattr(args, "labels", None))
        df, source, meta = loaded.df, loaded.source, loaded.meta()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    results, warns = run_experiment(df, models=models, split=args.split, seed=args.seed,
                                    threshold=args.threshold, explain=True)

    ablation_obj = None
    if args.ablate:
        from flowlab.eval.ablation import ablate
        ablation_obj = ablate(df, args.ablate, models=models, split=args.split,
                              seed=args.seed, threshold=args.threshold)

    from flowlab.payload import build_payload
    payload = build_payload(df, results, warns, source, meta,
                            ablation=ablation_obj.to_dict() if ablation_obj else None)
    return _finish(payload, args)
