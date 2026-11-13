"""特征矩阵构建：数值标准化 + 类别 one-hot + 缺失值填充。

只有一条构造路径 `_fit_preprocessor()`；三个公开函数只是"怎么切 train/test"的区别。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from flowlab.schema import META_COLUMNS, is_benign

# 端口与协议是名义变量，不是有序数值：一律 one-hot，避免"3333 < 5432"这种伪序关系
CATEGORICAL_FORCE = {"src_port", "dst_port", "protocol"}


@dataclass
class Prepared:
    X: np.ndarray
    y: np.ndarray
    feature_names: list[str]
    pipeline: ColumnTransformer
    raw: pd.DataFrame = field(repr=False, default=None)
    raw_features: list[str] = field(default_factory=list)


def _label_to_binary(labels: pd.Series) -> np.ndarray:
    """BENIGN/normal/0/False → 0，其余 → 1。"""
    return (~labels.map(is_benign)).astype(int).to_numpy()


def _features(df: pd.DataFrame, label_col: str | None = None,
              drop_extra: list[str] | None = None) -> pd.DataFrame:
    """丢掉元数据与标签，只留特征列；强制类别列转字符串。"""
    drop = (set(META_COLUMNS) | set(drop_extra or [])) & set(df.columns)
    if label_col:
        drop |= {label_col}
    feats = df.drop(columns=list(drop))
    feats = feats.loc[:, feats.notna().any(axis=0)]
    for c in CATEGORICAL_FORCE & set(feats.columns):
        feats[c] = feats[c].astype(str)
    return feats


def _make_preprocessor(feats: pd.DataFrame) -> ColumnTransformer:
    """唯一的预处理器工厂：数值中位数填充+标准化，类别众数填充+one-hot。"""
    num_cols = [c for c in feats.columns if pd.api.types.is_numeric_dtype(feats[c])]
    cat_cols = [c for c in feats.columns if c not in num_cols]

    transformers = []
    if num_cols:
        transformers.append(("num", Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("sc", StandardScaler()),
        ]), num_cols))
    if cat_cols:
        transformers.append(("cat", Pipeline([
            ("imp", SimpleImputer(strategy="most_frequent")),
            ("oh", OneHotEncoder(handle_unknown="ignore", min_frequency=10, sparse_output=False)),
        ]), cat_cols))

    return ColumnTransformer(transformers, remainder="drop", verbose_feature_names_out=False)


def build_matrix(df: pd.DataFrame, label_col: str = "label",
                 drop_extra: list[str] | None = None) -> Prepared:
    """整份数据上 fit（仅用于打分/探索；评估请用 build_matrix_pair）。"""
    if label_col not in df.columns:
        raise ValueError(f"缺少标签列 {label_col!r}，可用列: {list(df.columns)[:12]}")
    feats = _features(df, label_col=label_col, drop_extra=drop_extra)
    if feats.shape[1] == 0:
        raise ValueError("没有可用特征列")
    ct = _make_preprocessor(feats)
    X = np.asarray(ct.fit_transform(feats), dtype=float)
    return Prepared(X, _label_to_binary(df[label_col]),
                    list(ct.get_feature_names_out()), ct, feats, list(feats.columns))


def build_matrix_pair(train_df: pd.DataFrame, test_df: pd.DataFrame,
                      label_col: str = "label") -> tuple[Prepared, Prepared]:
    """严格版：预处理器只在训练集 fit，再 transform 测试集。"""
    if label_col not in train_df.columns or label_col not in test_df.columns:
        raise ValueError(f"缺少标签列 {label_col!r}")
    feats_tr = _features(train_df, label_col=label_col)
    feats_te = _features(test_df, label_col=label_col).reindex(columns=feats_tr.columns)
    if feats_tr.shape[1] == 0:
        raise ValueError("没有可用特征列")

    ct = _make_preprocessor(feats_tr)
    Xtr = np.asarray(ct.fit_transform(feats_tr), dtype=float)
    Xte = np.asarray(ct.transform(feats_te), dtype=float)
    names = list(ct.get_feature_names_out())
    raw_features = list(feats_tr.columns)
    return (
        Prepared(Xtr, _label_to_binary(train_df[label_col]), names, ct, feats_tr, raw_features),
        Prepared(Xte, _label_to_binary(test_df[label_col]), names, ct, feats_te, raw_features),
    )


def build_feature_matrix(df: pd.DataFrame, drop_extra: list[str] | None = None):
    """无标签数据（如 pcap）的特征矩阵：在本批数据上 fit，用于打分/排序。"""
    feats = _features(df, drop_extra=drop_extra)
    if feats.shape[1] == 0:
        raise ValueError("没有可用特征列")
    ct = _make_preprocessor(feats)
    return np.asarray(ct.fit_transform(feats), dtype=float), feats
