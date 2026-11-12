"""模型插件基类：所有模型只需要实现 fit / score。"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class Detector(ABC):
    name: str = "base"
    kind: str = "supervised"  # supervised | unsupervised

    def __init__(self, **params):
        self.params = params

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> "Detector":
        ...

    @abstractmethod
    def score(self, X: np.ndarray) -> np.ndarray:
        """返回异常分数，越大越可疑，范围约定 [0, 1]。"""

    def info(self) -> dict:
        return {"name": self.name, "kind": self.kind, "params": self.params}
