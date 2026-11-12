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
        self._clf = MLPClassifier(
            hidden_layer_sizes=tuple(hidden),
            activation="relu",
            solver="adam",
            alpha=1e-4,
            max_iter=max_iter,
            early_stopping=True,
            n_iter_no_change=15,
            random_state=seed,
            **extra,
        )

    def fit(self, X, y):
        self._clf.fit(X, y)
        return self

    def score(self, X):
        return self._clf.predict_proba(X)[:, 1]
