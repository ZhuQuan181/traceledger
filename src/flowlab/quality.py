"""标签质量诊断：在解释指标之前先暴露数据本身的冲突与长尾。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from flowlab.schema import is_benign

RARE_CLASS_THRESHOLD = 20


def _entity_key(df: pd.DataFrame) -> tuple[pd.Series, str] | None:
    if "flow_id" in df.columns and df["flow_id"].nunique(dropna=True) < len(df) * 0.95:
        return df["flow_id"].astype("string").fillna("<missing>"), "flow_id"
    five_tuple = ["src_ip", "dst_ip", "src_port", "dst_port", "protocol"]
    if all(column in df.columns for column in five_tuple):
        values = df[five_tuple].astype("string").fillna("<missing>").agg("|".join, axis=1)
        return values, "5-tuple"
    if "src_ip" in df.columns:
        return df["src_ip"].astype("string").fillna("<missing>"), "src_ip"
    return None


def _conflicts(df: pd.DataFrame, labels: pd.Series) -> dict:
    entity = _entity_key(df)
    if entity is None:
        return {
            "conflict_key": None,
            "conflict_groups": 0,
            "conflict_rows": 0,
            "conflict_examples": [],
        }

    keys, entity_label = entity
    valid = labels.notna() & labels.ne("")
    label_values = labels.loc[valid]
    frame = pd.DataFrame(
        {
            "_entity": keys.loc[valid],
            "_label": label_values,
            "_semantic": label_values.map(
                lambda value: "<BENIGN>" if is_benign(value) else str(value).strip()
            ),
        }
    )
    if frame.empty:
        return {
            "conflict_key": entity_label,
            "conflict_groups": 0,
            "conflict_rows": 0,
            "conflict_examples": [],
        }

    unique_labels = frame.groupby("_entity", dropna=False)["_semantic"].nunique(dropna=True)
    conflicting = unique_labels[unique_labels > 1]
    if conflicting.empty:
        return {
            "conflict_key": entity_label,
            "conflict_groups": 0,
            "conflict_rows": 0,
            "conflict_examples": [],
        }

    examples: list[dict[str, Any]] = []
    selected = frame[frame["_entity"].isin(conflicting.index)]
    for entity_value, group in selected.groupby("_entity", sort=False):
        values = sorted(
            {str(value).strip() for value in group["_label"].dropna() if str(value).strip()}
        )
        examples.append(
            {
                "entity": str(entity_value),
                "labels": values,
                "rows": int(len(group)),
            }
        )
        if len(examples) >= 5:
            break

    return {
        "conflict_key": entity_label,
        "conflict_groups": int(len(conflicting)),
        "conflict_rows": int(keys.isin(conflicting.index).sum()),
        "conflict_examples": examples,
    }


def label_quality(
    df: pd.DataFrame,
    label_col: str = "label",
    test_by_label: list[dict] | None = None,
) -> dict:
    """返回可序列化的标签质量摘要；不修改原数据。"""
    if label_col not in df.columns:
        return {}

    labels = df[label_col].astype("string").str.strip()
    missing = labels.isna() | labels.eq("")
    counts = labels.loc[~missing].value_counts()
    duplicate_rows = int(df.duplicated(keep=False).sum())
    conflicts = _conflicts(df, labels)
    rare_classes = [
        {"label": str(label), "count": int(count)}
        for label, count in counts.items()
        if int(count) < RARE_CLASS_THRESHOLD
    ]
    rare_test_labels = [
        {"label": str(row.get("label")), "total": int(row.get("total", 0))}
        for row in (test_by_label or [])
        if row.get("kind") == "attack" and int(row.get("total", 0)) < RARE_CLASS_THRESHOLD
    ]

    return {
        "rows": int(len(df)),
        "class_count": int(len(counts)),
        "missing_labels": int(missing.sum()),
        "duplicate_rows": duplicate_rows,
        "duplicate_rate": round(duplicate_rows / len(df), 4) if len(df) else 0.0,
        "rare_threshold": RARE_CLASS_THRESHOLD,
        "rare_classes": rare_classes,
        "rare_test_labels": rare_test_labels,
        **conflicts,
    }
