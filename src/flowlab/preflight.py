"""训练前数据预检：在启动长任务之前暴露列映射、切分覆盖和数据问题。"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from flowlab.eval.runner import dataset_hash
from flowlab.eval.split import plan_split
from flowlab.schema import META_COLUMNS, column_mapping, is_benign

_MISSING_LABELS = {"", "nan", "none", "null", "na", "n/a"}
_ROLES = {
    "label": "标签",
    "timestamp": "时间戳",
    "flow_id": "流标识",
    "src_ip": "源 IP",
    "dst_ip": "目的 IP",
    "src_port": "源端口",
    "dst_port": "目的端口",
    "protocol": "协议",
}


def _check(
    key: str,
    label: str,
    status: str,
    scope: str,
    detail: str,
    hint: str | None = None,
) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status,
        "scope": scope,
        "detail": detail,
        "hint": hint,
    }


def _label_mask(labels: pd.Series) -> pd.Series:
    normalized = labels.astype("string").str.strip().str.lower()
    return normalized.isna() | normalized.isin(_MISSING_LABELS)


def _non_finite_counts(df: pd.DataFrame, columns: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for column in columns:
        series = df[column]
        if pd.api.types.is_numeric_dtype(series):
            values = series.to_numpy(dtype=float, na_value=np.nan)
            count = int(np.isinf(values).sum())
        elif pd.api.types.is_object_dtype(series) or isinstance(series.dtype, pd.StringDtype):
            count = int(
                series.astype("string")
                .str.strip()
                .str.lower()
                .isin({"inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"})
                .sum()
            )
        else:
            count = 0
        if count:
            counts[column] = count
    return counts


def _split_coverage(df: pd.DataFrame, splits: dict[str, pd.Index], label_col: str) -> list[dict]:
    labels = df[label_col].astype("string").str.strip()
    benign = labels.map(is_benign)
    rows = []
    for name, index in splits.items():
        benign_count = int(benign.loc[index].sum())
        rows.append(
            {
                "split": name,
                "rows": int(len(index)),
                "benign": benign_count,
                "attack": int(len(index) - benign_count),
            }
        )
    return rows


def preflight_frame(
    df: pd.DataFrame,
    *,
    source: str,
    raw_columns: list[str] | None = None,
    split: str = "temporal",
    test_size: float = 0.3,
    validation_size: float = 0.2,
    seed: int = 42,
    label_col: str = "label",
) -> dict:
    """返回不训练模型的预检报告。

    评估与无标签评分是两条独立路径：没有标签时评分仍可运行，但完整评估会被阻断。
    """
    if split not in {"temporal", "random", "group"}:
        raise ValueError("split 只能是 temporal、random 或 group")
    if not 0.05 <= test_size <= 0.5:
        raise ValueError("test_size 应在 0.05~0.5 之间")
    if not 0.05 <= validation_size <= 0.4:
        raise ValueError("validation_size 应在 0.05~0.4 之间")
    if test_size + validation_size > 0.8:
        raise ValueError("test_size + validation_size 不能超过 0.8")

    rows = int(len(df))
    mapping = column_mapping(raw_columns or list(df.columns))
    canonical_counts: dict[str, int] = {}
    for row in mapping:
        row["role"] = _ROLES.get(row["canonical"])
        canonical_counts[row["canonical"]] = canonical_counts.get(row["canonical"], 0) + 1

    checks: list[dict] = []
    if rows < 20:
        checks.append(
            _check(
                "evaluation_rows",
                "评估样本量",
                "fail",
                "evaluation",
                f"只有 {rows} 行；三段切分与指标计算至少需要 20 行。",
                "增加样本，或改用无标签评分查看排序。",
            )
        )
    else:
        checks.append(
            _check(
                "evaluation_rows",
                "评估样本量",
                "pass",
                "evaluation",
                f"{rows:,} 行可用于训练/验证/测试切分。",
            )
        )
    checks.append(
        _check(
            "scoring_rows",
            "评分样本量",
            "pass" if rows >= 2 else "fail",
            "scoring",
            f"{rows:,} 行可进入无监督打分。" if rows >= 2 else "至少需要 2 行才能拟合与排序。",
        )
    )

    feature_columns = [
        column
        for column in df.columns
        if column not in META_COLUMNS and column != label_col and df[column].notna().any()
    ]
    checks.append(
        _check(
            "features",
            "可用特征",
            "pass" if feature_columns else "fail",
            "both",
            f"识别到 {len(feature_columns)} 个非全空特征列。"
            if feature_columns
            else "除了元数据与标签外，没有可用于训练的特征列。",
            None if feature_columns else "检查列名映射与 CSV 分隔符，确保至少有一列流量特征。",
        )
    )

    collisions = {canonical: count for canonical, count in canonical_counts.items() if count > 1}
    if collisions:
        examples = "、".join(f"{name} × {count}" for name, count in list(collisions.items())[:5])
        checks.append(
            _check(
                "column_collision",
                "列名冲突",
                "warn",
                "both",
                f"标准化后出现重复列（{examples}），目前只保留第一个。",
                "重命名原始列，避免多个列映射到同一标准名。",
            )
        )
    else:
        checks.append(
            _check("column_collision", "列名冲突", "pass", "both", "标准化后没有重复列。")
        )

    missing_counts = {column: int(df[column].isna().sum()) for column in feature_columns}
    missing_cells = sum(missing_counts.values())
    missing_columns = [
        {"column": column, "missing": count}
        for column, count in sorted(missing_counts.items(), key=lambda item: item[1], reverse=True)[
            :8
        ]
        if count
    ]
    if not feature_columns:
        missing_status = "warn"
    elif missing_cells == 0:
        missing_status = "pass"
    else:
        missing_status = "warn"
    checks.append(
        _check(
            "missing_values",
            "缺失值",
            missing_status,
            "both",
            f"特征区共 {missing_cells:,} 个空值；预处理会用中位数/众数填补。"
            if missing_cells
            else "特征区没有空值。",
            "若某列几乎全空，建议先在源头修复而不是依赖填补。" if missing_cells else None,
        )
    )

    non_finite = _non_finite_counts(df, feature_columns)
    non_finite_cells = sum(non_finite.values())
    checks.append(
        _check(
            "non_finite",
            "无限值",
            "pass" if non_finite_cells == 0 else "warn",
            "both",
            "没有 inf / infinity。"
            if non_finite_cells == 0
            else f"发现 {non_finite_cells:,} 个 inf；训练前会按缺失值清洗。",
            "速率类字段建议在原始特征计算阶段处理除零。" if non_finite_cells else None,
        )
    )

    timestamp_info: dict[str, Any] = {"column": None, "parse_rate": None, "invalid": None}
    if "timestamp" in df.columns:
        parsed = pd.to_datetime(df["timestamp"], errors="coerce", format="mixed")
        parse_rate = float(parsed.notna().mean()) if rows else 0.0
        invalid = int(rows - parsed.notna().sum())
        timestamp_info = {
            "column": "timestamp",
            "parse_rate": round(parse_rate, 4),
            "invalid": invalid,
        }
        if split == "temporal" and parse_rate < 0.9:
            checks.append(
                _check(
                    "timestamp",
                    "时间戳",
                    "warn",
                    "evaluation",
                    f"可解析 {parse_rate:.1%}，低于 90%；时间切分会退化为分层随机切分。",
                    "统一时间格式，或明确改用随机/实体分组切分并调整结论措辞。",
                )
            )
        else:
            checks.append(
                _check(
                    "timestamp",
                    "时间戳",
                    "pass" if parse_rate >= 0.9 else "warn",
                    "evaluation",
                    f"可解析 {parse_rate:.1%}。",
                )
            )
    elif split == "temporal":
        checks.append(
            _check(
                "timestamp",
                "时间戳",
                "warn",
                "evaluation",
                "没有 timestamp 列；时间切分会退化为分层随机切分。",
                "补时间戳，或改用随机切分并明确不能声称时间外推。",
            )
        )

    label_info: dict[str, Any] = {"present": label_col in df.columns, "classes": []}
    if label_col in df.columns:
        labels = df[label_col].astype("string").str.strip()
        missing_labels = int(_label_mask(labels).sum())
        valid_labels = labels.loc[~_label_mask(labels)]
        class_counts = valid_labels.value_counts()
        classes = [
            {
                "label": str(label),
                "count": int(count),
                "kind": "benign" if is_benign(label) else "attack",
            }
            for label, count in class_counts.items()
        ]
        benign_count = int(sum(row["count"] for row in classes if row["kind"] == "benign"))
        attack_count = int(sum(row["count"] for row in classes if row["kind"] == "attack"))
        label_info = {
            "present": True,
            "missing": missing_labels,
            "classes": classes,
            "benign": benign_count,
            "attack": attack_count,
        }
        if missing_labels:
            checks.append(
                _check(
                    "labels",
                    "标签",
                    "fail",
                    "evaluation",
                    f"{missing_labels:,} 行没有有效标签；未标注行不能被当作攻击样本。",
                    "补齐标签、过滤空标签行，或改用无标签评分。",
                )
            )
        elif benign_count == 0 or attack_count == 0:
            checks.append(
                _check(
                    "labels",
                    "标签",
                    "fail",
                    "evaluation",
                    f"标签只有单类（BENIGN {benign_count:,} / 攻击 {attack_count:,}）。",
                    "完整评估需要正常与攻击两类；无标签/单类数据可改做评分。",
                )
            )
        else:
            checks.append(
                _check(
                    "labels",
                    "标签",
                    "pass",
                    "evaluation",
                    f"BENIGN {benign_count:,} 行，攻击 {attack_count:,} 行。",
                )
            )
    else:
        checks.append(
            _check(
                "labels",
                "标签",
                "fail",
                "evaluation",
                "没有 label 列，无法计算 AUC/F1/误报率。",
                "补标签或上传旁挂标签文件；若目标只是排序，请使用无标签评分。",
            )
        )

    split_info: dict[str, Any] | None = None
    try:
        plan = plan_split(
            df,
            mode=split,
            test_size=test_size,
            validation_size=validation_size,
            seed=seed,
            label_col=label_col,
        )
        splits = {"train": plan.train, "validation": plan.validation, "test": plan.test}
        coverage = _split_coverage(df, splits, label_col) if label_col in df.columns else []
        split_info = {
            "requested": plan.requested,
            "effective": plan.effective,
            "fell_back": plan.fell_back,
            "coverage": coverage,
            "entity_key": plan.diagnostics.get("entity_key") or plan.diagnostics.get("group_key"),
            "warnings": plan.warnings,
        }
        checks.append(
            _check(
                "split",
                "切分计划",
                "warn" if plan.warnings else "pass",
                "evaluation",
                f"{plan.requested} → {plan.effective}；"
                f"训练 {len(plan.train):,} / 验证 {len(plan.validation):,} / "
                f"测试 {len(plan.test):,} 行。",
                " ".join(plan.warnings) if plan.warnings else None,
            )
        )
        if label_col in df.columns:
            for row in coverage:
                if row["benign"] == 0 or row["attack"] == 0:
                    checks.append(
                        _check(
                            f"coverage_{row['split']}",
                            f"{row['split']} 类别覆盖",
                            "fail",
                            "evaluation",
                            f"{row['split']} 集 BENIGN {row['benign']:,} / "
                            f"攻击 {row['attack']:,} 行，必须两类都有。",
                            "调整切分比例/方式或补充样本；时间切分尤其要检查攻击时段。",
                        )
                    )
                else:
                    checks.append(
                        _check(
                            f"coverage_{row['split']}",
                            f"{row['split']} 类别覆盖",
                            "pass",
                            "evaluation",
                            f"BENIGN {row['benign']:,} / 攻击 {row['attack']:,} 行。",
                        )
                    )
    except ValueError as exc:
        checks.append(
            _check(
                "split",
                "切分计划",
                "fail",
                "evaluation",
                str(exc),
                "调整切分方式、比例或补充实体/样本后再次预检。",
            )
        )

    def blockers(scope: str) -> list[str]:
        messages = []
        for row in checks:
            if row["status"] != "fail" or row["scope"] not in {scope, "both"}:
                continue
            messages.append(
                str(row["detail"]) if not row["hint"] else f"{row['detail']} {row['hint']}"
            )
        return messages

    evaluation_blockers = blockers("evaluation")
    scoring_blockers = blockers("scoring")
    return {
        "source": source,
        "dataset": {
            "rows": rows,
            "columns": int(len(df.columns)),
            "features": len(feature_columns),
            "hash": dataset_hash(df),
        },
        "column_mapping": mapping,
        "checks": checks,
        "missing": {"cells": missing_cells, "columns": missing_columns},
        "non_finite": {"cells": non_finite_cells, "columns": non_finite},
        "timestamp": timestamp_info,
        "labels": label_info,
        "split": split_info,
        "ready_for_evaluation": not evaluation_blockers,
        "ready_for_scoring": not scoring_blockers,
        "blockers": {
            "evaluation": evaluation_blockers,
            "scoring": scoring_blockers,
        },
    }
