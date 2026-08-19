# =============================================================================
# tests/test_classifier.py —— 多标签分类器
# =============================================================================

import numpy as np
import pytest

from app.ml.classifier import TagClassifier


def _X(n_samples=4, n_features=50):
    rng = np.random.RandomState(0)
    return rng.rand(n_samples, n_features)


def test_predict_returns_scored_tags_descending():
    X = _X()
    y = [{"math"}, {"physics"}, {"math", "physics"}, {"chemistry"}]
    clf = TagClassifier(threshold=0.0, top_k=10).train(X, y)
    preds = clf.predict(X)
    assert len(preds) == 4
    for tags in preds:
        scores = [s for _, s in tags]
        assert scores == sorted(scores, reverse=True)  # 置信度降序
        assert all(0.0 <= s <= 1.0 for s in scores)


def test_top_k_bounds_result():
    X = _X()
    y = [{"a"}, {"b"}, {"c"}, {"d"}]
    clf = TagClassifier(threshold=0.0, top_k=2).train(X, y)
    for tags in clf.predict(X):
        assert len(tags) <= 2


def test_threshold_filters_low_confidence():
    X = _X()
    y = [{"a"}, {"b"}, {"c"}, {"d"}]
    clf = TagClassifier(threshold=0.5, top_k=10).train(X, y)
    for tags in clf.predict(X):
        assert all(s >= 0.5 for _, s in tags)


def test_predict_not_fitted_returns_empty():
    clf = TagClassifier()
    preds = clf.predict(np.zeros((3, 10)))
    assert preds == [[], [], []]


def test_train_requires_two_distinct_tags():
    clf = TagClassifier()
    with pytest.raises(ValueError):
        clf.train(np.zeros((2, 5)), [{"math"}, {"math"}])


def test_confidence_clamps_to_unit_interval():
    assert TagClassifier.confidence(-0.5) == 0.0
    assert TagClassifier.confidence(0.7) == 0.7
    assert TagClassifier.confidence(1.5) == 1.0
