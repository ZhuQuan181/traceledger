"""特征矩阵构建：数值标准化 + 类别 one-hot + 缺失值填充。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from flowlab.schema import META_COLUMNS

BENIGN = "benign"


@dataclass
class Prepared:
    X: np.ndarray
    y: np.ndarray
    feature_names: list[str]
    pipeline: ColumnTransformer
    raw: pd.DataFrame = field(repr=False, default=None)


def _label_to_binary(labels: pd.Series) -> np.ndarray:
    return (labels.astype(str).str.strip().str.lower() != BENIGN).astype(int).to_numpy()


def build_matrix(df: pd.DataFrame, label_col: str = "label", drop_extra: list[str] | None = None) -> Prepared:
    """把标准化后的 DataFrame 变成模型可吃的矩阵。

    - label 列二值化：BENIGN -> 0，其余 -> 1
    - 元数据列（IP/端口/时间/id）不参与训练
    - 返回的 pipeline 已 fit，可直接用于新数据 transform
    """
    if label_col not in df.columns:
        raise ValueError(f"缺少标签列 {label_col!r}，可用列: {list(df.columns)[:12]}")

    drop = (set(META_COLUMNS) | set(drop_extra or [])) & set(df.columns)
    drop.discard(label_col)
    feats = df.drop(columns=list(drop))

    # 全空列直接丢
    feats = feats.loc[:, feats.notna().any(axis=0)]
    if feats.shape[1] == 0:
        raise ValueError("没有可用特征列")

    num_cols = [c for c in feats.columns if pd.api.types.is_numeric_dtype(feats[c])]
    cat_cols = [c for c in feats.columns if c not in num_cols]

    transformers = []
    if num_cols:
        transformers.append(("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                                               ("sc", StandardScaler())]), num_cols))
    if cat_cols:
        transformers.append(("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                                               ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), cat_cols))

    ct = ColumnTransformer(transformers, remainder="drop", verbose_feature_names_out=False)
    X = ct.fit_transform(feats)
    names = list(ct.get_feature_names_out())
    y = _label_to_binary(df[label_col])
    return Prepared(X=np.asarray(X, dtype=float), y=y, feature_names=names, pipeline=ct, raw=feats)


def build_matrix_pair(train_df: pd.DataFrame, test_df: pd.DataFrame,
                      label_col: str = "label") -> tuple[Prepared, Prepared]:
    """严格版：预处理器只在训练集上 fit，再 transform 测试集。"""
    if label_col not in train_df.columns or label_col not in test_df.columns:
        raise ValueError(f"缺少标签列 {label_col!r}")

    drop = (set(META_COLUMNS)) & set(train_df.columns)
    drop.discard(label_col)
    feats_tr = train_df.drop(columns=list(drop))
    feats_te = test_df.drop(columns=[c for c in drop if c in test_df.columns])
    keep = [c for c in feats_tr.columns if feats_tr[c].notna().any()]
    feats_tr, feats_te = feats_tr[keep], feats_te[[c for c in keep if c in feats_te.columns]]

    num_cols = [c for c in keep if pd.api.types.is_numeric_dtype(feats_tr[c])]
    cat_cols = [c for c in keep if c not in num_cols]
    transformers = []
    if num_cols:
        transformers.append(("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                                               ("sc", StandardScaler())]), num_cols))
    if cat_cols:
        transformers.append(("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                                               ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), cat_cols))

    ct = ColumnTransformer(transformers, remainder="drop", verbose_feature_names_out=False)
    Xtr = np.asarray(ct.fit_transform(feats_tr), dtype=float)
    Xte = np.asarray(ct.transform(feats_te.reindex(columns=keep)), dtype=float)
    names = list(ct.get_feature_names_out())
    return (
        Prepared(Xtr, _label_to_binary(train_df[label_col]), names, ct, feats_tr),
        Prepared(Xte, _label_to_binary(test_df[label_col]), names, ct, feats_te),
    )


def build_feature_matrix(df: pd.DataFrame, drop_extra: list[str] | None = None):
    """无标签数据（如 pcap）的特征矩阵：在本批数据上 fit，用于打分/排序。"""
    drop = (set(META_COLUMNS) | set(drop_extra or [])) & set(df.columns)
    feats = df.drop(columns=list(drop))
    feats = feats.loc[:, feats.notna().any(axis=0)]
    num_cols = [c for c in feats.columns if pd.api.types.is_numeric_dtype(feats[c])]
    cat_cols = [c for c in feats.columns if c not in num_cols]
    transformers = []
    if num_cols:
        transformers.append(("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                                               ("sc", StandardScaler())]), num_cols))
    if cat_cols:
        transformers.append(("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                                               ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), cat_cols))
    ct = ColumnTransformer(transformers, remainder="drop", verbose_feature_names_out=False)
    X = np.asarray(ct.fit_transform(feats), dtype=float)
    return X, feats
