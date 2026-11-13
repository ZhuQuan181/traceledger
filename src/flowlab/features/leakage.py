"""数据泄漏检测：在训练之前，先把"会让指标虚高"的列找出来。

三类规则：
1. id_leak    —— 唯一标识列（flow_id / 长字符串）被当成特征
2. time_leak  —— 有时间戳却用随机切分（未来信息进训练集）
3. port_leak  —— 某个端口在某类攻击里占比 > 90%（模型学到的是端口，不是行为）
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from flowlab.schema import is_benign


def _is_benign(value: Any) -> bool:
    return is_benign(value)


def detect(df: pd.DataFrame, split: str = "temporal", label_col: str = "label") -> list[dict]:
    """返回泄漏警告列表，每条含 rule / columns / severity / message / suggestion。"""
    warns: list[dict] = []
    n = len(df)
    if n == 0:
        return warns

    # 1) 唯一标识列
    id_like = []
    for col in df.columns:
        if col == label_col:
            continue
        s = df[col]
        if s.nunique(dropna=True) >= 0.95 * n:
            if col == "flow_id" or s.dtype == object or col.endswith("_id"):
                id_like.append(col)
    if id_like:
        warns.append(
            {
                "rule": "id_leak",
                "columns": id_like,
                "severity": "high",
                "message": f"{len(id_like)} 列几乎每行都不同（{', '.join(id_like[:3])}），是标识符而非特征。",
                "suggestion": "训练前丢弃这些列；它们只适合做去重与追溯。",
            }
        )

    # 2) 时间戳 + 随机切分
    if "timestamp" in df.columns and split == "random":
        warns.append(
            {
                "rule": "time_leak",
                "columns": ["timestamp"],
                "severity": "high",
                "message": "数据带时间戳，但使用了随机切分：测试集的'未来'会出现在训练集里。",
                "suggestion": "改用时间切分（--split temporal），或确认数据本身无时间相关性。",
            }
        )

    # 3) 端口泄漏
    if "dst_port" in df.columns and label_col in df.columns and df[label_col].nunique() > 1:
        for cls, grp in df.groupby(label_col, dropna=True):
            if _is_benign(cls) or len(grp) < 10:
                continue
            share = grp["dst_port"].value_counts(normalize=True)
            if len(share) and share.iloc[0] > 0.90:
                warns.append(
                    {
                        "rule": "port_leak",
                        "columns": ["dst_port"],
                        "severity": "medium",
                        "message": f"类别 {cls} 中有 {share.iloc[0]:.1%} 的流目的端口是 {share.index[0]}。",
                        "suggestion": "先确认这是业务特征还是数据集构造痕迹；若为构造痕迹，去掉端口列重跑对比。",
                    }
                )

    # 4) 目标泄漏：某列几乎一对一决定标签（如 attack_type / category）
    if label_col in df.columns:
        y = df[label_col].astype(str).str.strip().str.lower()
        n_classes = y.nunique()
        for col in df.columns:
            if col == label_col or col in id_like:
                continue
            s = df[col]
            if s.nunique(dropna=True) <= 1 or s.nunique(dropna=True) > 50:
                continue
            # 每个取值对应的标签是否唯一
            grouped = df.groupby(col, dropna=True)[label_col].nunique(dropna=True)
            if len(grouped) and (grouped <= 1).mean() >= 0.95 and len(grouped) <= max(20, n_classes):
                warns.append(
                    {
                        "rule": "target_leak",
                        "columns": [col],
                        "severity": "high",
                        "message": f"`{col}` 的每个取值几乎只对应一个标签类别，等于把答案交给了模型。",
                        "suggestion": "训练前删掉该列；它是标注结果，不是可观测特征。",
                    }
                )

    # 5) 常量列
    const = [c for c in df.columns if c != label_col and df[c].nunique(dropna=False) <= 1]
    if const:
        warns.append(
            {
                "rule": "constant_column",
                "columns": const,
                "severity": "low",
                "message": f"{len(const)} 列取值恒定，对模型无信息量。",
                "suggestion": "可删除以加速训练。",
            }
        )

    return warns


def summarize(warns: list[dict]) -> str:
    if not warns:
        return "未检测到明显的特征/切分泄漏。"
    lines = [f"[{w['severity'].upper()}] {w['rule']}: {w['message']}" for w in warns]
    return "\n".join(lines)
