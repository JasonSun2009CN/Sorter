# =============================================================================
# tests/test_extractor.py —— 内容文本提取
# =============================================================================

import pytest

from app.core import extractor


def test_extract_plain_text(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("hello world", encoding="utf-8")
    assert extractor.extract_text(p) == "hello world"


def test_extract_markdown(tmp_path):
    p = tmp_path / "readme.md"
    p.write_text("# Title\n\nSome **bold** text.", encoding="utf-8")
    text = extractor.extract_text(p)
    assert text is not None
    assert "Title" in text
    assert "bold" in text


def test_extract_pdf(tmp_path):
    try:
        import pymupdf
    except ImportError:  # pragma: no cover
        pytest.skip("pymupdf not installed")
    p = tmp_path / "doc.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "extract me from pdf")
    doc.save(str(p))
    doc.close()
    assert extractor.extract_text(p) == "extract me from pdf"


def test_extract_docx(tmp_path):
    try:
        from docx import Document
    except ImportError:  # pragma: no cover
        pytest.skip("python-docx not installed")
    p = tmp_path / "doc.docx"
    doc = Document()
    doc.add_paragraph("extract me from docx")
    doc.save(str(p))
    assert extractor.extract_text(p) == "extract me from docx"


def test_unsupported_extension_returns_none(tmp_path):
    p = tmp_path / "blob.xyz"
    p.write_bytes(b"\x00\x01\x02")
    assert extractor.extract_text(p) is None


def test_image_returns_none(tmp_path):
    p = tmp_path / "pic.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    assert extractor.extract_text(p) is None


def test_missing_file_returns_none(tmp_path):
    assert extractor.extract_text(tmp_path / "nope.txt") is None


def test_text_truncated_to_max_chars(tmp_path):
    p = tmp_path / "long.txt"
    p.write_text("a" * (extractor.MAX_TEXT_CHARS + 100), encoding="utf-8")
    text = extractor.extract_text(p)
    assert text is not None
    assert len(text) <= extractor.MAX_TEXT_CHARS
