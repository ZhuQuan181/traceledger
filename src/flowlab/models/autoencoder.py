"""基线二：最小自编码器（只用正常样本训练，以重构误差作为异常分）。"""
from __future__ import annotations

import numpy as np
from sklearn.neural_network import MLPRegressor

from flowlab.models.base import Detector
from flowlab.models.registry import register


@register("autoencoder")
class AutoEncoderDetector(Detector):
    kind = "unsupervised"

    def __init__(self, hidden=(16, 8, 16), max_iter: int = 300, seed: int = 42, **extra):
        super().__init__(hidden_layer_sizes=hidden, max_iter=max_iter, seed=seed, **extra)
        self._reg = MLPRegressor(hidden_layer_sizes=tuple(hidden), activation="relu",
                                 max_iter=max_iter, random_state=seed, early_stopping=True, **extra)
        self._hi = 1.0

    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        train = X[np.asarray(y) == 0] if y is not None and (np.asarray(y) == 0).sum() >= 20 else X
        self._reg.fit(train, train)
        err = ((self._reg.predict(train) - train) ** 2).mean(axis=1)
        self._hi = float(np.quantile(err, 0.99)) or 1.0
        return self

    def score(self, X):
        X = np.asarray(X, dtype=float)
        err = ((self._reg.predict(X) - X) ** 2).mean(axis=1)
        return np.clip(err / max(self._hi, 1e-9), 0.0, 1.0)
