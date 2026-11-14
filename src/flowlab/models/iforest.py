"""基线一：Isolation Forest（无监督，不需要标签）。"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest

from flowlab.models.base import Detector
from flowlab.models.registry import register


@register("iforest")
class IForestDetector(Detector):
    kind = "unsupervised"

    def __init__(self, n_estimators: int = 200, seed: int = 42, **extra):
        super().__init__(n_estimators=n_estimators, seed=seed, **extra)
        self._clf = IsolationForest(
            n_estimators=n_estimators, random_state=seed, n_jobs=-1, **extra
        )
        self._lo = 0.0
        self._hi = 1.0

    def fit(self, X, y=None):
        self._clf.fit(X)
        s = -self._clf.score_samples(X)
        self._lo, self._hi = float(np.quantile(s, 0.50)), float(np.quantile(s, 0.995))
        return self

    def score(self, X):
        s = -self._clf.score_samples(X)
        span = max(self._hi - self._lo, 1e-9)
        return np.clip((s - self._lo) / span, 0.0, 1.0)
