# =============================================================================
# app/gui/formatting.py —— 展示格式化（纯函数，不依赖 Qt）
#
# 作用：
#   把文件大小 / 时间戳转成界面友好的字符串，与 Qt 解耦以便单测。
#
# 结构：
#   format_size(n) -> str    # B / KB / MB / GB，保留一位小数
#   format_mtime(ts) -> str  # "%Y-%m-%d %H:%M"（本地时区）
# =============================================================================

"""文件大小与时间戳的展示格式化。"""

from __future__ import annotations

from datetime import datetime

_UNITS = ["B", "KB", "MB", "GB", "TB"]


def format_size(n: int) -> str:
    """把字节数格式化为人类可读大小，如 1536 -> "1.5 KB"。"""
    size = float(n)
    for unit in _UNITS:
        if size < 1024 or unit == _UNITS[-1]:
            return f"{size:.1f} {unit}".replace(".0 ", " ")
        size /= 1024
    return f"{n} B"


def format_mtime(ts: float) -> str:
    """把时间戳格式化为本地时间 "%Y-%m-%d %H:%M"。"""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
