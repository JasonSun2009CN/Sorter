# =============================================================================
# tests/test_formatting.py —— 展示格式化（纯函数）
# =============================================================================

from app.gui.formatting import format_mtime, format_size


def test_format_size_bytes():
    assert format_size(0) == "0 B"
    assert format_size(512) == "512 B"


def test_format_size_units():
    assert format_size(1536) == "1.5 KB"
    assert format_size(1024 * 1024) == "1 MB"
    assert format_size(2 * 1024 * 1024 * 1024) == "2 GB"


def test_format_mtime():
    # 2026-08-19 12:34:00 UTC+8
    ts = __import__("datetime").datetime(2026, 8, 19, 12, 34).timestamp()
    assert format_mtime(ts) == "2026-08-19 12:34"
