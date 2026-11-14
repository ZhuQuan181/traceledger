"""消融：把可疑列拿掉重跑，让"指标掉了多少"变成可看到的数字。

最常用的是 `--ablate dst_port`：端口在某个攻击类里占比 96% 时，
去掉它 AUC 从 1.0 掉到 0.6，说明模型学到的是数据集构造痕迹。
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from flowlab.eval.runner import EvalResult, run_experiment


@dataclass
class Ablation:
    column: str
    with_column: list[EvalResult]
    without_column: list[EvalResult]

    def deltas(self) -> list[dict]:
        by_model = {r.model: r for r in self.without_column}
        rows = []
        for r in self.with_column:
            other = by_model.get(r.model)
            if other is None:
                continue
            auc_a = r.metrics.get("auc")
            auc_b = other.metrics.get("auc")
            rows.append(
                {
                    "model": r.model,
                    "auc_with": auc_a,
                    "auc_without": auc_b,
                    "delta": None if (auc_a is None or auc_b is None) else round(auc_a - auc_b, 4),
                }
            )
        return rows

    def to_dict(self) -> dict:
        return {
            "column": self.column,
            "rows": self.deltas(),
            "note": f"去掉 `{self.column}` 后重跑，Δ 为 AUC 变化（正值 = 该列在撑指标）。",
        }


def ablate(df: pd.DataFrame, column: str, **run_kwargs) -> Ablation:
    if column not in df.columns:
        raise ValueError(f"要消融的列 {column!r} 不存在，可用列: {list(df.columns)[:15]}")
    base, _ = run_experiment(df, **run_kwargs)
    stripped, _ = run_experiment(df.drop(columns=[column]), **run_kwargs)
    return Ablation(column=column, with_column=base, without_column=stripped)


def format_table(ab) -> str:
    column = ab.column if isinstance(ab, Ablation) else ab["column"]
    rows = ab.deltas() if isinstance(ab, Ablation) else ab.get("rows", [])
    lines = [
        f"== 消融：去掉 {column} ==",
        "| 模型 | 含该列 AUC | 去掉后 AUC | Δ |",
        "|---|---|---|---|",
    ]
    for row in rows:
        a = "—" if row["auc_with"] is None else f"{row['auc_with']:.4f}"
        b = "—" if row["auc_without"] is None else f"{row['auc_without']:.4f}"
        d = "—" if row["delta"] is None else f"{row['delta']:+.4f}"
        lines.append(f"| {row['model']} | {a} | {b} | {d} |")
    return "\n".join(lines)
