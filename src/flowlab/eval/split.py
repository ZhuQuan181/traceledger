"""切分策略：默认时间切分，避免未来信息泄漏。"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import pandas as pd

from flowlab.schema import is_benign, normalize_name


@dataclass
class SplitPlan:
    train: pd.Index
    validation: pd.Index
    test: pd.Index
    requested: str
    effective: str
    warnings: list[str] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)

    @property
    def fell_back(self) -> bool:
        return self.requested == "temporal" and self.effective != "temporal"


def _timestamp_series(df: pd.DataFrame) -> pd.Series | None:
    for col in df.columns:
        if normalize_name(col) == "timestamp":
            return pd.to_datetime(df[col], errors="coerce", format="mixed")
    return None


def _coverage_warnings(
    df: pd.DataFrame, splits: list[tuple[str, pd.Index]], label_col: str
) -> list[str]:
    if label_col not in df.columns:
        return []
    out: list[str] = []
    for name, idx in splits:
        attack_count = (~df.loc[idx, label_col].map(is_benign)).sum()
        if attack_count == 0:
            out.append(
                f"{name}中没有攻击样本（{len(idx)} 行全为 BENIGN）。"
                "时间切分下这通常意味着攻击集中在某个时段，建议调整 test_size 或改用分层时间切分。"
            )
    return out


def _entity_series(df: pd.DataFrame) -> tuple[pd.Series, str] | None:
    """按强度依次选实体键：flow_id > 五元组 > 源 IP。"""
    if "flow_id" in df.columns and df["flow_id"].nunique(dropna=True) < len(df) * 0.95:
        return df["flow_id"].astype("string").fillna("<missing>"), "flow_id"
    five_tuple = ["src_ip", "dst_ip", "src_port", "dst_port", "protocol"]
    if all(column in df.columns for column in five_tuple):
        key = df[five_tuple].astype("string").fillna("<missing>").agg("|".join, axis=1)
        return key, "5-tuple"
    if "src_ip" in df.columns:
        return df["src_ip"].astype("string").fillna("<missing>"), "src_ip"
    return None


def _split_diagnostics(
    df: pd.DataFrame,
    train: pd.Index,
    validation: pd.Index,
    test: pd.Index,
) -> tuple[dict, list[str]]:
    """找出完全重复行与实体重叠；行级切分最容易在这里制造乐观偏差。"""
    row_hash = pd.util.hash_pandas_object(df, index=False)
    hashes = {
        "train": set(row_hash.loc[train].tolist()),
        "validation": set(row_hash.loc[validation].tolist()),
        "test": set(row_hash.loc[test].tolist()),
    }
    duplicate_cross = {
        "train_validation": len(hashes["train"] & hashes["validation"]),
        "train_test": len(hashes["train"] & hashes["test"]),
        "validation_test": len(hashes["validation"] & hashes["test"]),
    }
    diagnostics: dict = {
        "duplicate_rows": int(df.duplicated(keep=False).sum()),
        "duplicate_cross": duplicate_cross,
        "entity_key": None,
        "entity_overlap": {},
    }
    warnings: list[str] = []
    if any(duplicate_cross.values()):
        total = sum(duplicate_cross.values())
        warnings.append(
            f"训练/验证/测试之间存在 {total:,} 个完全重复内容；"
            "行级切分会把同一流量重复计入指标，建议去重或使用 --split group。"
        )

    entity = _entity_series(df)
    if entity is not None:
        series, label = entity
        groups = {
            "train": set(series.loc[train].tolist()),
            "validation": set(series.loc[validation].tolist()),
            "test": set(series.loc[test].tolist()),
        }
        overlap = {
            "train_validation": len(groups["train"] & groups["validation"]),
            "train_test": len(groups["train"] & groups["test"]),
            "validation_test": len(groups["validation"] & groups["test"]),
        }
        diagnostics["entity_key"] = label
        diagnostics["entity_overlap"] = overlap
        if any(overlap.values()):
            total = sum(overlap.values())
            warnings.append(
                f"按 {label} 统计，有 {total:,} 个实体同时出现在多个子集中；"
                "若结论要泛化到新主机/新会话，请使用 --split group。"
            )
    return diagnostics, warnings


def plan_split(
    df: pd.DataFrame,
    mode: str = "temporal",
    test_size: float = 0.3,
    validation_size: float = 0.2,
    seed: int = 42,
    label_col: str = "label",
) -> SplitPlan:
    """返回切分计划，并明确记录最终使用的模式。

    temporal: 按时间排序，依次划出训练、验证、测试；时间不可解析时退化为 random。
    random:   分层随机切分（仅在你确认数据无时间相关性时使用）。
    group:    按实体（flow_id / 五元组 / src_ip）分组，同一实体只落在一个子集。

    test_size 与 validation_size 都是整份数据的比例。验证集只用于模型选择，
    测试集只在最后报告一次指标。
    """
    if mode not in {"temporal", "random", "group"}:
        raise ValueError("split 只能是 temporal、random 或 group")
    if not 0.05 <= test_size <= 0.5:
        raise ValueError("test_size 应在 0.05~0.5 之间")
    if not 0.05 <= validation_size <= 0.4:
        raise ValueError("validation_size 应在 0.05~0.4 之间")
    if test_size + validation_size > 0.8:
        raise ValueError("test_size + validation_size 不能超过 0.8，训练集至少保留 20%")
    if len(df) < 20:
        raise ValueError("样本太少（<20 行），无法切分")

    ts = _timestamp_series(df) if mode == "temporal" else None
    effective = mode
    split_warnings: list[str] = []
    diagnostics: dict = {}
    if mode == "group":
        from sklearn.model_selection import GroupShuffleSplit

        entity = _entity_series(df)
        if entity is None:
            raise ValueError(
                "分组切分需要 flow_id、五元组或 src_ip 中至少一组列；当前数据没有可用实体键。"
            )
        groups, entity_label = entity
        splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
        try:
            train_pool, test = next(splitter.split(df, groups=groups))
            val_fraction = validation_size / max(1e-9, 1 - test_size)
            splitter = GroupShuffleSplit(
                n_splits=1,
                test_size=val_fraction,
                random_state=seed,
            )
            train, validation = next(
                splitter.split(df.iloc[train_pool], groups=groups.iloc[train_pool])
            )
            train = train_pool[train]
            validation = train_pool[validation]
        except ValueError as exc:
            raise ValueError(
                "实体数量不足以同时划出训练、验证和测试集；请增加样本或改用 --split random。"
            ) from exc
        train, validation, test = pd.Index(train), pd.Index(validation), pd.Index(test)
        diagnostics["group_key"] = entity_label
    elif ts is not None and ts.notna().sum() >= len(df) * 0.9:
        order = ts.sort_values(kind="mergesort").index
        train_end = int(len(order) * (1 - test_size - validation_size))
        validation_end = int(len(order) * (1 - test_size))
        train = pd.Index(order[:train_end])
        validation = pd.Index(order[train_end:validation_end])
        test = pd.Index(order[validation_end:])
    else:
        if mode == "temporal":
            effective = "random"
            split_warnings.append(
                "请求了时间切分，但时间戳缺失或可解析比例不足 90%，"
                "已退化为分层随机切分；这组指标不再具备时间外推含义。"
            )
        from sklearn.model_selection import train_test_split

        stratify = (
            df[label_col] if label_col in df.columns and df[label_col].nunique() > 1 else None
        )
        train_pool, test = train_test_split(
            df.index, test_size=test_size, random_state=seed, stratify=stratify
        )
        val_fraction = validation_size / max(1e-9, 1 - test_size)
        validation_stratify = df.loc[train_pool, label_col] if stratify is not None else None
        if validation_stratify is not None and validation_stratify.value_counts().min() < 2:
            validation_stratify = None
        try:
            train, validation = train_test_split(
                train_pool,
                test_size=val_fraction,
                random_state=seed,
                stratify=validation_stratify,
            )
        except ValueError as exc:
            raise ValueError(
                "无法在保持类别比例的同时划出验证集；请增加样本量或降低 validation_size。"
            ) from exc
        train, validation, test = pd.Index(train), pd.Index(validation), pd.Index(test)

    split_warnings.extend(
        _coverage_warnings(
            df,
            [("训练集", train), ("验证集", validation), ("测试集", test)],
            label_col,
        )
    )
    overlap_diagnostics, overlap_warnings = _split_diagnostics(df, train, validation, test)
    diagnostics.update(overlap_diagnostics)
    split_warnings.extend(overlap_warnings)
    return SplitPlan(
        train=train,
        validation=validation,
        test=test,
        requested=mode,
        effective=effective,
        warnings=split_warnings,
        diagnostics=diagnostics,
    )


def split_indices(
    df: pd.DataFrame,
    mode: str = "temporal",
    test_size: float = 0.3,
    validation_size: float = 0.2,
    seed: int = 42,
    label_col: str = "label",
) -> tuple[pd.Index, pd.Index]:
    """兼容旧调用的二元组接口。

    旧接口没有验证集，因此把验证集并回训练侧，保持 train + test = 全部数据，
    同时保留时间顺序与实体不重叠约束。新代码应使用 plan_split 获取三段切分。
    """
    plan = plan_split(
        df,
        mode=mode,
        test_size=test_size,
        validation_size=validation_size,
        seed=seed,
        label_col=label_col,
    )
    for message in plan.warnings:
        warnings.warn(message, RuntimeWarning, stacklevel=2)
    return plan.train.append(plan.validation), plan.test
