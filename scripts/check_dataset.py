"""数据集体检：在任何训练之前，先回答"这份 CSV 到底能不能用"。

用法：
  uv run python scripts/check_dataset.py path/to/file.csv
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from flowlab.ingest import read_any
from flowlab.schema import BENIGN_ALIASES, is_benign, normalize_columns

LABEL_CANDIDATES = ("label", "labels", "class", "attack", "y", "target", "is_attack")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    a = ap.parse_args()

    try:
        df, info = read_any(a.file, allow_pickle=True)
    except Exception as exc:  # noqa: BLE001 - CLI 边界必须把任意读取错误转成可读提示
        print(f"✗ 读取失败：{exc}")
        return 2
    df = normalize_columns(df)

    print(f"文件      {a.file}")
    print(f"格式      {info.get('format')}  形状 {info.get('shape')}")
    print(f"行 × 列   {df.shape[0]:,} × {df.shape[1]}")
    print()

    label_col = next((c for c in df.columns if c in LABEL_CANDIDATES), None)
    problems = 0

    if label_col is None:
        print("✗ 找不到标签列（label/labels/class/attack/y/target/is_attack）")
        problems += 1
    else:
        counts = df[label_col].astype(str).str.strip().value_counts()
        print(f"标签列    {label_col}（{counts.size} 类）")
        for k, v in counts.head(10).items():
            print(f"  {k:<24} {v:>9,}  {v / len(df):6.2%}")
        benign = sum(v for k, v in counts.items() if is_benign(k))
        print(f"  正常样本合计           {benign:>9,}  {benign / len(df):6.2%}")
        if counts.size < 2:
            print("✗ 只有一类标签，无法做二分类评估")
            problems += 1
        if benign == 0:
            print(
                "✗ 没有正常样本；BENIGN 同义词集合："
                + ", ".join(sorted(BENIGN_ALIASES)[:6])
                + " ..."
            )
            problems += 1

    num = df.select_dtypes(include=[np.number])
    inf_cols = [c for c in num.columns if np.isinf(num[c]).any()]
    nan_ratio = num.isna().mean().sort_values(ascending=False).head(3)
    print()
    print(f"数值列    {num.shape[1]}")
    if inf_cols:
        print(f"⚠ 含 inf 的列（{len(inf_cols)}）：{', '.join(inf_cols[:6])}")
        problems += 1
    else:
        print("⚠ 含 inf 的列：无")
    for c, r in nan_ratio.items():
        if r > 0:
            print(f"  缺失率最高 {c}: {r:.1%}")

    dup = int(df.duplicated().sum())
    print(f"重复行    {dup:,}" + ("  ⚠ 建议去重后再切分" if dup else ""))

    print()
    if problems:
        print(f"结论：发现 {problems} 个阻断问题，先修数据再训练。")
    else:
        print("结论：可以训练。推荐命令：")
        print(
            f"  uv run flowlab run {a.file} --split temporal --report out/report.md --html out/report.html"
        )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
