# =============================================================================
# tests/test_features.py —— TF-IDF 特征提取
# =============================================================================

import numpy as np

from app.core.scanner import ScannedFile
from app.ml import features


def _make_file(path, text):
    path.write_text(text, encoding="utf-8")
    return ScannedFile(path=path, size=path.stat().st_size, mtime=0.0, ctime=0.0)


def test_build_corpus_includes_name_parent_and_text(tmp_path):
    p = tmp_path / "math_notes.txt"
    f = _make_file(p, "calculus derivative integral")
    corpus = features.build_corpus([f])
    assert len(corpus) == 1
    assert "math" in corpus[0] and "notes" in corpus[0]  # 文件名（_ 转空格）
    assert tmp_path.name in corpus[0]  # 父目录名
    assert ".txt" in corpus[0]         # 扩展名
    assert "calculus" in corpus[0]     # 提取文本


def test_vectorizer_roundtrip_consistent(tmp_path):
    files = [
        _make_file(tmp_path / "math.txt", "calculus derivative integral"),
        _make_file(tmp_path / "physics.txt", "force velocity acceleration"),
    ]
    corpus = features.build_corpus(files)
    X, vectorizer = features.fit_transform(corpus)
    X2 = features.transform(features.build_corpus(files), vectorizer)
    assert X.shape == X2.shape
    assert X.shape[0] == 2
    # 同一语料：fit_transform 与 transform 在浮点精度内一致
    assert np.allclose(X.toarray(), X2.toarray(), atol=1e-10)


def test_transform_new_documents_same_feature_space(tmp_path):
    files = [
        _make_file(tmp_path / "a.txt", "alpha beta gamma"),
        _make_file(tmp_path / "b.txt", "delta epsilon zeta"),
    ]
    X, vectorizer = features.fit_transform(features.build_corpus(files))
    new = [_make_file(tmp_path / "c.txt", "eta theta iota")]
    X_new = features.transform(features.build_corpus(new), vectorizer)
    assert X_new.shape[1] == X.shape[1]  # 特征维度与训练一致
    assert X_new.shape[0] == 1


def test_chinese_filenames_produce_features(tmp_path):
    p = tmp_path / "数学笔记.txt"
    f = _make_file(p, "微积分 导数 积分")
    corpus = features.build_corpus([f])
    X, _ = features.fit_transform(corpus)
    assert X.shape[0] == 1
    assert X.shape[1] > 0  # 中文文件名 / 文本应产生字符 n-gram 特征
