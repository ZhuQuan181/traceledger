"""最基础的监督模型：两层 MLP。"""
from __future__ import annotations

import numpy as np
from sklearn.neural_network import MLPClassifier

from flowlab.models.base import Detector
from flowlab.models.registry import register


@register("mlp")
class MLPDetector(Detector):
    kind = "supervised"

    def __init__(self, hidden=(64, 32), max_iter: int = 300, seed: int = 42, **extra):
        super().__init__(hidden_layer_sizes=hidden, max_iter=max_iter, seed=seed, **extra)
        self._hidden = tuple(hidden)
        self._max_iter = max_iter
        self._seed = seed
        self._extra = extra
        self._clf: MLPClassifier | None = None

    def fit(self, X, y):
        # 小样本时 sklearn 的验证集切分会失败，关掉 early_stopping
        early = len(X) >= 200
        self._clf = MLPClassifier(
            hidden_layer_sizes=self._hidden,
            activation="relu",
            solver="adam",
            alpha=1e-4,
            max_iter=self._max_iter,
            early_stopping=early,
            n_iter_no_change=30 if early else 5,
            validation_fraction=0.15,
            random_state=self._seed,
            **self._extra,
        )
        self._clf.fit(X, y)
        return self

    def score(self, X):
        assert self._clf is not None, "先 fit 再 score"
        proba = self._clf.predict_proba(X)
        # 训练集只有一个类别时，predict_proba 只有一列
        return proba[:, 1] if proba.shape[1] > 1 else proba[:, 0] * 0

    def score(self, X):
        return self._clf.predict_proba(X)[:, 1]
