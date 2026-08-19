# =============================================================================
# app/ml/features.py —— 特征提取
#
# 作用：
#   将文件名、路径、提取到的文本拼成语料，经 TF-IDF 转为
#   分类器可用的数值特征矩阵。
#
# 大致结构：
#   def build_corpus(files) -> list[str]         # 文件名 + 路径 + 文本
#   def make_vectorizer() -> TfidfVectorizer
#   def fit_transform(corpus) -> (X, vectorizer) # 训练阶段
#   def transform(corpus, vectorizer) -> X       # 预测阶段
# =============================================================================
