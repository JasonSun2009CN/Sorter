# =============================================================================
# app/ml/classifier.py —— 标签分类器
#
# 作用：
#   用轻量、CPU 友好的模型预测标签，并为每个预测给出置信度分数。
#   优先可解释性：Logistic Regression / Linear SVM / Naive Bayes。
#
# 大致结构：
#   class TagClassifier
#       train(X, y)                              # 训练模型
#       predict(features) -> list[(tag, score)]  # 预测 + 置信度
#       confidence(scores) -> float              # 归一化置信度
# =============================================================================
