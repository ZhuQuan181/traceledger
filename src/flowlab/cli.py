"""FlowLab 命令行入口。

结构：
  cli 只负责解析参数、打印、写文件；
  真正的编排在 service.execute()，与 API 共用。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from flowlab.eval.table import markdown_table
from flowlab.features.leakage import summarize
from flowlab.pipeline import load_frame
from flowlab.service import ExperimentSpec, demo_frame, execute, results_of, score_frame


def _add_run_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--models", default="mlp,iforest,autoencoder")
    p.add_argument("--split", default="temporal", choices=["temporal", "random"])
    p.add_argument("--test-size", type=float, default=0.3, help="测试集比例（0.05~0.5）")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--json", action="store_true")
    p.add_argument("--report", type=Path, help="Markdown 报告输出路径")
    p.add_argument("--html", type=Path, help="单文件 HTML 报告输出路径")
    p.add_argument("--ablate", metavar="COLUMN", help="去掉该列重跑，报出指标变化")
    p.add_argument("--no-save", action="store_true", help="不写入本地实验历史")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="flowlab", description="流量异常检测研究/实验工作台")
    sub = p.add_subparsers(dest="cmd")

    d = sub.add_parser("demo", help="用合成数据跑一次完整实验")
    d.add_argument("--normal", type=int, default=5000)
    d.add_argument("--attack", type=int, default=500)
    d.add_argument(
        "--leaky", action="store_true", help="生成只有端口不同的极端数据，用来演示端口泄漏"
    )
    _add_run_flags(d)

    r = sub.add_parser("run", help="对数据文件跑实验")
    r.add_argument("file", type=Path)
    r.add_argument("--labels", type=Path, help="旁挂标签（pcap 或纯特征文件用）")
    r.add_argument(
        "--allow-pickle",
        action="store_true",
        help="允许加载 pickle（会执行反序列化代码，仅限可信文件）",
    )
    _add_run_flags(r)

    s = sub.add_parser("score", help="对无标签数据打分，输出最可疑的流")
    s.add_argument("file", type=Path)
    s.add_argument("--model", default="iforest")
    s.add_argument("--top", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--labels", type=Path)
    s.add_argument("--allow-pickle", action="store_true")

    sv = sub.add_parser("serve", help="启动本地 Web 界面")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8765)

    h = sub.add_parser("history", help="最近的实验（本地 SQLite）")
    h.add_argument("--limit", type=int, default=20)
    h.add_argument("--prune", type=int, metavar="KEEP", help="只保留最近 KEEP 条，其余删除")

    sh = sub.add_parser("show", help="查看某次实验，可导出报告")
    sh.add_argument("run_id")
    sh.add_argument("--html", type=Path)
    sh.add_argument("--md", type=Path)

    cm = sub.add_parser("compare", help="对比多次实验的最佳指标")
    cm.add_argument("run_ids", nargs="+")

    sm = sub.add_parser("sample", help="生成一份样例 CSV，用来试跑或给同事")
    sm.add_argument("--rows", type=int, default=2000)
    sm.add_argument("--out", type=Path, default=Path("sample_flows.csv"))
    sm.add_argument("--leaky", action="store_true", help="生成带端口泄漏的极端样例")

    sub.add_parser("formats", help="列出支持的数据格式")
    sub.add_parser("models", help="列出已注册模型")
    return p


def _finish(payload: dict, args) -> int:
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("== 数据泄漏检查 ==")
        print(summarize(payload["warnings"]))
        print()
        print("== 模型对比 ==")
        print(markdown_table(results_of(payload)))
        if payload.get("ablation"):
            from flowlab.eval.ablation import format_table

            print()
            print(format_table(payload["ablation"]))

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
        print(
            f"实验已记录：{rid}（flowlab show {rid}）", file=sys.stderr if args.json else sys.stdout
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd is None:
        build_parser().print_help()
        return 0

    if args.cmd == "sample":
        from flowlab.schema import normalize_columns
        from flowlab.synthetic import generate

        n_attack = max(10, args.rows // 10)
        df = normalize_columns(
            generate(
                n_normal=args.rows - n_attack, n_attack=n_attack, seed=42, leakage_only=args.leaky
            )
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.out, index=False)
        print(f"样例已写入 {args.out}（{len(df):,} 行，{n_attack:,} 条攻击）")
        print(f"下一步：uv run flowlab run {args.out} --split temporal --html out/sample.html")
        return 0

    if args.cmd == "formats":
        from flowlab.ingest import supported_formats

        print("\n".join(supported_formats()))
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
        from flowlab.store import count, list_runs, prune

        if args.prune is not None:
            removed = prune(args.prune)
            print(f"已清理 {removed} 条，剩余 {count()} 条。")
            return 0
        runs = list_runs(args.limit)
        if not runs:
            print("还没有实验记录。跑一次 `flowlab demo`。")
            return 0
        print(f"{'ID':<12} {'时间':<20} {'数据':<30} {'最佳模型':<12} {'AUC':>7}")
        for r in runs:
            auc = "—" if r["best_auc"] is None else f"{r['best_auc']:.4f}"
            print(
                f"{r['id']:<12} {(r['created_at'] or '')[:19]:<20} "
                f"{(r['source'] or '')[:28]:<30} {(r['best_model'] or '—'):<12} {auc:>7}"
            )
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
        print(markdown_table(results_of(payload)))
        for path, key, label in (
            (args.md, "report_md", "Markdown"),
            (args.html, "report_html", "HTML"),
        ):
            if path:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(payload[key], encoding="utf-8")
                print(f"{label} 报告：{path}")
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
            delta = (
                ""
                if (auc is None or base["best_auc"] is None)
                else f"{auc - base['best_auc']:+.4f}"
            )
            print(
                f"{rec['id']:<12} {(rec['source'] or '')[:22]:<24} {(rec['best_model'] or '—'):<12} "
                f"{('—' if auc is None else f'{auc:.4f}'):>8} {delta:>10}"
            )
        return 0

    if args.cmd == "score":
        if not args.file.exists():
            print(f"文件不存在: {args.file}", file=sys.stderr)
            return 2
        try:
            loaded = load_frame(
                args.file,
                getattr(args, "labels", None),
                allow_pickle=getattr(args, "allow_pickle", False),
            )
        except Exception as exc:  # noqa: BLE001 - CLI 边界统一转成退出码与提示
            print(f"读取失败: {exc}", file=sys.stderr)
            return 2
        rows = score_frame(loaded.df, model=args.model, top=args.top)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            print(f"== Top {len(rows)} 可疑流（模型 {args.model}，共 {len(loaded.df)} 条）==")
            if loaded.label_info:
                print(f"   标签对齐: {loaded.label_info}")
            print(pd.DataFrame(rows).to_string(index=False))
        return 0

    # demo / run
    if args.cmd == "demo":
        spec = ExperimentSpec(
            models=[m.strip() for m in args.models.split(",") if m.strip()],
            split=args.split,
            seed=args.seed,
            threshold=args.threshold,
            test_size=args.test_size,
            ablate=args.ablate or None,
            source_kind="demo",
            normal=args.normal,
            attack=args.attack,
            leaky=args.leaky,
        )
        df, meta, source = demo_frame(args.normal, args.attack, args.seed, args.leaky)
    else:
        if not args.file.exists():
            print(f"文件不存在: {args.file}", file=sys.stderr)
            return 2
        try:
            loaded = load_frame(args.file, args.labels, allow_pickle=args.allow_pickle)
        except Exception as exc:  # noqa: BLE001 - CLI 边界统一转成退出码与提示
            print(f"读取失败: {exc}", file=sys.stderr)
            return 2
        df, source, meta = loaded.df, loaded.source, loaded.meta()
        spec = ExperimentSpec(
            models=[m.strip() for m in args.models.split(",") if m.strip()],
            split=args.split,
            seed=args.seed,
            threshold=args.threshold,
            test_size=args.test_size,
            ablate=args.ablate or None,
            source_kind="file",
            source_ref=str(args.file),
        )

    try:
        payload = execute(df, meta, source, spec)
    except ValueError as exc:
        print(f"实验失败: {exc}", file=sys.stderr)
        return 2
    return _finish(payload, args)
