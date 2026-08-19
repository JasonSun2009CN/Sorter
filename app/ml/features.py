# =============================================================================
# app/ml/features.py —— 特征提取
#
# 作用：
#   将文件名、路径、提取到的文本拼成语料，经 TF-IDF 转为
#   分类器可用的数值特征矩阵。
#
# 结构：
#   build_corpus(files) -> list[str]         # 文件名 + 路径 + 扩展名 + 文本
#   make_vectorizer() -> TfidfVectorizer
#   fit_transform(corpus) -> (X, vectorizer) # 训练阶段
#   transform(corpus, vectorizer) -> X       # 预测阶段
# =============================================================================

"""TF-IDF 特征提取：文件名 + 路径 + 扩展名 + 提取文本 → 数值特征矩阵。"""

from __future__ import annotations

from collections.abc import Iterable

from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from app.core.extractor import extract_text
from app.core.scanner import ScannedFile

# 向量器默认参数
# analyzer='char_wb' + ngram_range=(2,4)：对中文（无空格分词）与英文文件名
# 同样健壮；词边界内取字符 n-gram，避免跨词拼出无意义特征。
VECTORIZER_KWARGS: dict = {
    "analyzer": "char_wb",
    "ngram_range": (2, 4),
    "min_df": 1,
    "sublinear_tf": True,
    "strip_accents": "unicode",
    "max_features": 20_000,
}


def build_corpus(files: Iterable[ScannedFile]) -> list[str]:
    """把每个文件拼成一条语料文本：文件名（去扩展名）+ 父目录 + 扩展名 + 提取文本。

    文件名与目录里的下划线 / 连字符会替换为空格，为 char_wb 提供词边界。
    """
    corpus: list[str] = []
    for f in files:
        stem = f.path.stem.replace("_", " ").replace("-", " ")
        parent = f.path.parent.name
        text = extract_text(f.path) or ""
        corpus.append(f"{stem} {parent} {f.extension} {text}".strip())
    return corpus


def make_vectorizer() -> TfidfVectorizer:
    """构造配置统一的 TF-IDF 向量器。"""
    return TfidfVectorizer(**VECTORIZER_KWARGS)


def fit_transform(corpus: list[str]) -> tuple[sparse.csr_matrix, TfidfVectorizer]:
    """在训练语料上拟合并转换，返回 (特征矩阵, 向量器)。"""
    vectorizer = make_vectorizer()
    X = vectorizer.fit_transform(corpus)
    return X, vectorizer


def transform(corpus: list[str], vectorizer: TfidfVectorizer) -> sparse.csr_matrix:
    """用已拟合的向量器转换新语料（与训练保持同一特征空间）。"""
    return vectorizer.transform(corpus)
