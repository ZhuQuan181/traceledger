"""规模基准：生成 N 行合成流量，量一遍 ingest → features → train → score 的墙钟时间。

用法：
  uv run python scripts/bench_scale.py --rows 100000
  uv run python scripts/bench_scale.py --rows 690000 --models mlp,iforest
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from flowlab.engineer import add_engineered_features
from flowlab.eval.runner import run_experiment
from flowlab.ingest.csv import read_csv
from flowlab.synthetic import generate


def timed(label: str, fn):
    t0 = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t0
    print(f"{label:<26} {dt:8.2f}s")
    return out, dt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=100_000, help="总行数（按 9:1 拆正常/攻击）")
    ap.add_argument("--models", default="iforest")
    ap.add_argument("--split", default="temporal")
    ap.add_argument("--keep-csv", action="store_true")
    a = ap.parse_args()

    n_attack = max(10, a.rows // 10)
    n_normal = a.rows - n_attack
    csv_path = Path("/tmp") / f"bench_{a.rows}.csv"

    raw, t_gen = timed(f"生成 {a.rows:,} 行", lambda: generate(n_normal, n_attack, seed=42))
    timed("写 CSV", lambda: raw.to_csv(csv_path, index=False))
    size_mb = csv_path.stat().st_size / 2**20

    df, t_read = timed("读 CSV + 列名标准化", lambda: read_csv(csv_path))
    df, t_feat = timed("特征工程", lambda: add_engineered_features(df))

    results, warns = timed(
        f"跑模型 {a.models}",
        lambda: run_experiment(
            df, models=[m.strip() for m in a.models.split(",")], split=a.split, seed=42
        ),
    )[0]

    print()
    print(f"文件大小            {size_mb:8.1f} MB")
    print(f"列数                {df.shape[1]:8d}")
    print(f"内存峰值(近似)      {df.memory_usage(deep=False).sum() / 2**20:8.1f} MB")
    print()
    for r in results:
        m = r.metrics
        auc = "—" if m.get("auc") is None else f"{m['auc']:.4f}"
        print(
            f"{r.model:<12} AUC {auc}  F1 {m['f1']:.4f}  耗时 {r.duration_s:.2f}s"
            f"  训练 {r.n_train:,} / 测试 {r.n_test:,}"
        )
    print()
    print(f"总耗时（不含生成）  {t_read + t_feat + sum(r.duration_s for r in results):8.2f}s")

    if not a.keep_csv:
        csv_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
