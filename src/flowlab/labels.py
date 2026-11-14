"""旁挂标签：pcap 本身没有 ground truth，用一个 CSV 补上。

支持三种对齐方式，按优先级：
1. flow_id   —— 标签文件里有 flow_id 列，按 id 合并
2. 五元组     —— (src_ip, dst_ip, src_port, dst_port, protocol) 交集列合并；
               同一五元组多条流时，只要有一条是攻击就标为攻击（保守）
3. 位置       —— 标签文件只有一列 `label`，且行数与流数一致，按顺序赋值
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from flowlab.ingest import read_any
from flowlab.schema import is_benign as _is_benign_value
from flowlab.schema import normalize_columns

KEYS = ["src_ip", "dst_ip", "src_port", "dst_port", "protocol"]


def _is_benign(series: pd.Series) -> pd.Series:
    return series.map(_is_benign_value)


def attach_labels(flows: pd.DataFrame, labels_path: str | Path) -> tuple[pd.DataFrame, dict]:
    """返回 (带 label 的 DataFrame, 对齐报告)。无法对齐时抛 ValueError。"""
    lab_raw, _format = read_any(labels_path, allow_pickle=False)
    if not isinstance(lab_raw, pd.DataFrame):
        raise ValueError("标签文件必须包含二维表格，而不是标量或一维数组")
    lab = normalize_columns(lab_raw)
    if "label" not in lab.columns:
        raise ValueError(f"标签文件缺少 label 列，实际列: {list(lab.columns)[:10]}")

    info = {"mode": None, "labelled": 0, "total": len(flows), "matches": 0}

    # 1) flow_id
    if "flow_id" in lab.columns and "flow_id" in flows.columns:
        merged = flows.merge(
            lab[["flow_id", "label"]].drop_duplicates("flow_id"), on="flow_id", how="left"
        )
        if merged["label"].notna().sum():
            info.update(
                mode="flow_id",
                labelled=int(merged["label"].notna().sum()),
                matches=int(len(merged)),
            )
            return merged, info

    # 2) 五元组
    keys = [k for k in KEYS if k in lab.columns and k in flows.columns]
    if len(keys) >= 3:

        def _merge_labels(s: pd.Series) -> str:
            if _is_benign(s).all():
                return "BENIGN"
            # 保留具体的攻击类型（DDoS / PortScan ...），便于报告里看出是什么攻击
            bad = [v for v, benign in zip(s, _is_benign(s)) if not benign]
            return str(bad[0]) if bad else "ATTACK"

        agg = lab.groupby(keys, dropna=False)["label"].agg(_merge_labels).reset_index()
        merged = flows.merge(agg, on=keys, how="left")
        # 二进制标签用 BENIGN / ATTACK 表示，避免把具体攻击类型压平后失去信息
        if merged["label"].notna().sum():
            info.update(
                mode="+".join(keys),
                labelled=int(merged["label"].notna().sum()),
                matches=int(merged["label"].notna().sum()),
            )
            return merged, info

    # 3) 行序
    if len(lab) == len(flows):
        out = flows.copy()
        out["label"] = lab["label"].to_numpy()
        info.update(mode="row_order", labelled=len(out), matches=len(out))
        return out, info

    raise ValueError(
        f"无法对齐标签：标签文件 {len(lab)} 行，流 {len(flows)} 行；"
        f"可用键 {keys or '无'}。请提供 flow_id 或五元组列，或保持行数与流数一致。"
    )


def guess_sidecar(path: str | Path) -> Path | None:
    """自动寻找 <name>.labels.csv / <name>_labels.csv。"""
    p = Path(path)
    for cand in (p.with_suffix(p.suffix + ".labels.csv"), p.with_name(p.stem + "_labels.csv")):
        if cand.exists():
            return cand
    return None
