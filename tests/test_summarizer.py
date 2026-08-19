# =============================================================================
# tests/test_summarizer.py —— 内容概述与关键词（纯逻辑）
# =============================================================================

from app.core.summarizer import build_summaries, keywords, summarize
from app.core.scanner import ScannedFile
from pathlib import Path


def test_keywords_english_filters_stopwords():
    text = "the calculus derivative integral calculus integral integral limit theorem"
    assert keywords(text, top_n=3) == ["integral", "calculus", "derivative"] or \
        set(keywords(text, top_n=3)) == {"integral", "calculus", "derivative"}


def test_keywords_top_n_and_deterministic():
    text = "apple banana cherry apple banana apple date"
    kw = keywords(text, top_n=3)
    assert kw[0] == "apple"
    assert keywords(text, top_n=3) == kw  # 稳定


def test_keywords_chinese_runs_and_bigrams():
    text = "数学微积分笔记 数学微积分笔记 物理力学 物理力学"
    kw = keywords(text, top_n=8)
    # 7 字段 → 重叠 2-gram（数学/积分…）
    assert "数学" in kw and "积分" in kw
    # 4 字段（≤5）整段保留
    assert "物理力学" in kw


def test_keywords_empty():
    assert keywords(None) == []
    assert keywords("") == []
    assert keywords("the and or 的 了") == []  # 全是停用词


def test_summarize_composes():
    meta = {"width": 1920, "height": 1080, "date": "2024:01:01 12:00:00"}
    out = summarize("calculus derivative integral", meta, name="photo.jpg")
    assert out is not None
    assert "类型：image" in out
    assert "关键词" in out
    assert "1920×1080" in out
    assert "2024" in out


def test_summarize_none_for_empty():
    assert summarize(None, {}) is None


def test_summarize_meta_only():
    out = summarize(None, {"width": 100, "height": 50}, name="a.png")
    assert out is not None
    assert "100×50" in out


def test_summarize_pdf_pages():
    out = summarize("some text", {"pages": 12}, name="a.pdf")
    assert "页数 12" in out


def test_build_summaries():
    files = [ScannedFile(path=Path("/tmp/a.txt"), size=1, mtime=0.0, ctime=0.0)]
    texts = {"/tmp/a.txt": "alpha beta gamma alpha"}
    out = build_summaries(files, texts)
    assert len(out) == 1
    assert out[0][0] == "/tmp/a.txt"
    assert "alpha" in out[0][1]
