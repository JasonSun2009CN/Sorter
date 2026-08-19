# =============================================================================
# app/core/extractor.py —— 内容文本提取
#
# 作用：
#   从常见文档 / 文本文件中尽力提取纯文本，作为 ML 分类的输入特征。
#   解析失败或不可解析的文件返回 None，不影响主流程。
#
# 结构：
#   extract_text(path) -> str | None     # 按扩展名分发解析器
#   _read_text(path)                     # 纯文本 / 代码类文件
#   _extract_pdf(path)                   # PyMuPDF
#   _extract_docx(path)                  # python-docx
#   _extract_image(path)                 # Pillow（占位，MVP 不含 OCR）
# =============================================================================

"""内容文本提取：从常见文档 / 文本文件中尽力提取纯文本。"""

from __future__ import annotations

from pathlib import Path

# 纯文本 / 代码类扩展名：直接按 UTF-8 读取（errors=replace 兜底）
TEXT_EXTS: frozenset[str] = frozenset({
    ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv",
    ".log", ".json", ".xml", ".html", ".htm",
    ".py", ".js", ".ts", ".java", ".c", ".h", ".cpp", ".go", ".rs",
    ".yml", ".yaml", ".ini", ".cfg", ".toml", ".sql",
})

# 文本截断上限，控制 TF-IDF 特征规模与训练耗时
MAX_TEXT_CHARS = 100_000


def extract_text(path: str | Path) -> str | None:
    """按扩展名分发解析器提取纯文本；失败或不可解析返回 None。"""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in TEXT_EXTS:
        return _read_text(p)
    if ext == ".pdf":
        return _extract_pdf(p)
    if ext == ".docx":
        return _extract_docx(p)
    return None  # 其它格式（含图片，MVP 无 OCR）


def _read_text(path: Path) -> str | None:
    """读取 UTF-8 文本文件；缺失 / 无权限时返回 None。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return _clean(fh.read())
    except OSError:
        return None


def _clean(text: str) -> str:
    """折叠空白并截断长度；空文本返回空字符串。"""
    return " ".join(text.split())[:MAX_TEXT_CHARS]


def _extract_pdf(path: Path) -> str | None:
    """用 PyMuPDF 逐页提取文本；库缺失或解析失败返回 None。"""
    try:
        import pymupdf
    except ImportError:  # 兼容旧版本包名 fitz
        try:
            import fitz as pymupdf
        except ImportError:
            return None
    parts: list[str] = []
    try:
        with pymupdf.open(path) as doc:
            for page in doc:
                parts.append(page.get_text())
    except Exception:
        return None
    return _clean("\n".join(parts)) or None


def _extract_docx(path: Path) -> str | None:
    """用 python-docx 提取段落与表格文本；库缺失或解析失败返回 None。"""
    try:
        from docx import Document
    except ImportError:
        return None
    try:
        doc = Document(str(path))
    except Exception:
        return None
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" ".join(cell.text for cell in row.cells))
    return _clean("\n".join(parts)) or None


def _extract_image(path: Path) -> str | None:
    """图片提取（OCR）暂不在 MVP 范围，保留扩展点。"""
    return None
