# =============================================================================
# app/ml/classifier.py —— 标签分类器
#
# 作用：
#   用轻量、CPU 友好的模型预测标签，并为每个预测给出置信度分数。
#   优先可解释性：OneVsRest + Logistic Regression，支持多标签（一个文件
#   可有多个标签），每个标签独立给出一元概率作为置信度。
#
# 结构：
#   class TagClassifier
#       train(X, y)                              # 训练模型（y: 每样本的标签集合）
#       predict(X) -> [[(tag, score), ...], ...] # 预测 + 置信度，降序
#       confidence(score) -> float               # 归一化置信度
# =============================================================================

"""多标签文本分类器：OneVsRest Logistic Regression + 置信度。"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer


class TagClassifier:
    """多标签分类器。

    - 标签集通过 ``MultiLabelBinarizer`` 转为指示矩阵，每个标签一个二元分类器；
    - ``predict`` 返回每文件 [(标签, 置信度), ...]，按置信度降序，并受
      ``threshold`` 与 ``top_k`` 约束；
    - 未训练时 ``predict`` 对每个样本返回空列表（不抛错）。
    """

    def __init__(
        self,
        *,
        threshold: float = 0.35,
        top_k: int = 3,
        max_iter: int = 1000,
    ) -> None:
        self.threshold = threshold
        self.top_k = top_k
        self._mlb = MultiLabelBinarizer()
        self._model = OneVsRestClassifier(LogisticRegression(max_iter=max_iter))
        self._fitted = False
        self.classes_: list[str] = []

    def train(self, X, y: Iterable[Iterable[str]]) -> "TagClassifier":
        """训练模型。``y`` 为每样本一个可迭代的标签名集合。

        要求训练数据至少包含 2 个不同标签，否则抛 ``ValueError``。
        """
        y_bin = self._mlb.fit_transform([sorted(set(tags)) for tags in y])
        if y_bin.shape[1] < 2:
            raise ValueError("训练数据需要至少 2 个不同的标签")
        self._model.fit(X, y_bin)
        self._fitted = True
        self.classes_ = list(self._mlb.classes_)
        return self

    def predict(self, X) -> list[list[tuple[str, float]]]:
        """为每个样本预测 [(标签, 置信度), ...]，置信度降序。"""
        n = X.shape[0]
        if not self._fitted:
            return [[] for _ in range(n)]
        proba = self._model.predict_proba(X)
        # 多标签场景下 predict_proba 可能返回每个类一个数组的列表，
        # 统一拼成 (n_samples, n_classes) 矩阵。
        if isinstance(proba, list):
            proba = np.column_stack(proba) if proba else np.zeros((n, 0))
        return [self._rank(row) for row in proba]

    def _rank(self, row: np.ndarray) -> list[tuple[str, float]]:
        scored = [
            (cls, self.confidence(float(score)))
            for cls, score in zip(self.classes_, row)
        ]
        scored.sort(key=lambda t: t[1], reverse=True)
        return [
            (cls, score) for cls, score in scored if score >= self.threshold
        ][: self.top_k]

    @staticmethod
    def confidence(score: float) -> float:
        """归一化置信度到 [0, 1]（predict_proba 输出本就在区间内，裁剪兜底）。"""
        return max(0.0, min(1.0, float(score)))
