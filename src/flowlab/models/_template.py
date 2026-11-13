"""接入你自己的模型：复制这个文件，改三处，就能出现在模型列表里。

用法（30 行以内）：
    1. cp src/flowlab/models/_template.py src/flowlab/models/my_model.py
    2. 改 @register("...") 里的名字
    3. 在 fit() 里训练、在 score() 里返回异常分
    4. uv run flowlab models    # 应该能看到 my_model

契约（很少，但必须守）：
    fit(X, y) -> self
        X: (n_samples, n_features) 的 float ndarray，已标准化、类别已 one-hot
        y: (n_samples,) 的 0/1 数组，0=BENIGN，1=攻击；无监督模型可忽略
        小样本注意：n < 200 时别开 early_stopping，sklearn 会因验证集太小报错

    score(X) -> ndarray, shape (n_samples,)
        越大越可疑，必须落在 [0, 1]；框架用 threshold（默认 0.5）判定

    kind = "supervised" | "unsupervised"
        supervised 会检查训练集是否有正样本；unsupervised 不做检查
"""
from __future__ import annotations

import numpy as np

from flowlab.models.base import Detector
from flowlab.models.registry import register


@register("my_model")
class MyDetector(Detector):
    kind = "supervised"          # 改成 "unsupervised" 表示不用标签

    def __init__(self, threshold_hint: float = 0.5, seed: int = 42, **extra):
        super().__init__(threshold_hint=threshold_hint, seed=seed, **extra)
        self._model = None
        self._seed = seed

    def fit(self, X: np.ndarray, y: np.ndarray):
        # ── 在这里训练你的模型 ──
        # 下面这行只是占位：用逻辑回归演示"最后要能给出概率"
        from sklearn.linear_model import LogisticRegression

        X = np.asarray(X, dtype=float)
        if y is None or len(np.unique(y)) < 2:
            # 无监督场景：用一个仓库里已有的基线兜底，避免本模板报错
            from flowlab.models.iforest import IForestDetector

            self._model = IForestDetector(seed=self._seed).fit(X, None)
        else:
            self._model = LogisticRegression(max_iter=1000, random_state=self._seed).fit(X, y)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        assert self._model is not None, "先 fit 再 score"
        if hasattr(self._model, "predict_proba"):
            return np.asarray(self._model.predict_proba(X))[:, 1]
        return np.clip(np.asarray(self._model.score(X), dtype=float), 0.0, 1.0)
