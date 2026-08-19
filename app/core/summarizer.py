# =============================================================================
# app/core/summarizer.py —— 内容概述与关键词
#
# 作用：
#   从提取到的文本中抽出高频关键词，并生成一行为主的可读概述
#   （类型 · 关键词 + 内容预览 + 元数据）。纯逻辑、可单测，不依赖 Qt。
#
# 关键词做法（Counter + 正则，非 TF-IDF）：
#   单文档的 IDF 无意义，char n-gram 也不适合人类可读标签。这里：
#   - ASCII 词（≥3 字符，含 -_）
#   - 中文整段（≤5 字）或重叠 2-gram（长句 → 稳定双字词）
#   - 过滤停用词（英文虚词 + 中文助词 + 代码噪声）
#
# 结构：
#   keywords(text, top_n=3) -> list[str]
#   summarize(text, meta, *, name) -> str | None
#   build_summaries(files, texts) -> [(path, summary)]
# =============================================================================

"""内容概述：关键词抽取与可读概述生成。"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable

from app.core import metadata
from app.core.extractor import extract_metadata
from app.core.scanner import ScannedFile

_ASCII_TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]{2,}")  # 至少 3 字符
_CJK_RUN = re.compile(r"[一-鿿]{2,}")

_STOPWORDS: frozenset[str] = frozenset({
    # 英文虚词
    "the", "and", "for", "with", "this", "that", "from", "have", "has", "was",
    "were", "are", "you", "your", "not", "but", "all", "can", "its", "will",
    "about", "into", "their", "they", "them", "then", "than", "which", "when",
    "what", "there", "here", "would", "should", "could", "may", "might", "also",
    "very", "just", "like", "one", "two", "new", "more", "most", "some", "such",
    "only", "over", "under", "after", "before", "during", "between", "through",
    "against", "without", "within", "upon", "because", "where", "been", "being",
    "out", "back", "off", "up", "down", "in", "on", "at", "to", "of", "by",
    "is", "it", "be", "or", "an", "if", "as",
    # 代码噪声
    "def", "import", "return", "class", "null", "true", "false", "none", "self",
    "print", "elif", "else", "while", "with", "not", "and", "or", "is",
    # 中文助词 / 高频虚词
    "的", "了", "是", "和", "在", "与", "及", "或", "有", "这", "那", "之",
    "为", "对", "从", "把", "被", "让", "就", "都", "也", "很", "更", "而",
    "但", "并", "又", "且", "等", "一个", "我们", "你们", "他们", "自己",
})


def _tokens(text: str) -> list[str]:
    """混合中英文 token 化：ASCII 词 + 中文整段/2-gram。"""
    tokens: list[str] = []
    tokens.extend(_ASCII_TOKEN.findall(text.lower()))
    for run in _CJK_RUN.findall(text):
        if len(run) <= 5:
            tokens.append(run)
        else:
            tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    return tokens


def keyword_scores(
    text: str | None,
    top_n: int = 3,
    *,
    stopwords: frozenset[str] = _STOPWORDS,
) -> list[tuple[str, float]]:
    """返回 (关键词, 归一化频次) 列表（同频按字典序稳定排序）。

    score = 频次 / 最高频次，首词恒为 1.0，供自动打标签的置信度使用。
    """
    if not text:
        return []
    counts = Counter(
        tok for tok in _tokens(text)
        if tok not in stopwords and len(tok) >= 2
    )
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    if not ranked:
        return []
    top_count = ranked[0][1]
    return [(tok, round(count / top_count, 3)) for tok, count in ranked[:top_n]]


def keywords(
    text: str | None,
    top_n: int = 3,
    *,
    stopwords: frozenset[str] = _STOPWORDS,
) -> list[str]:
    """返回出现频次最高的 top_n 个关键词（同频按字典序稳定排序）。"""
    return [tok for tok, _ in keyword_scores(text, top_n, stopwords=stopwords)]


def _meta_bits(meta: dict) -> list[str]:
    """把元数据渲染成可读片段。"""
    bits: list[str] = []
    if "width" in meta and "height" in meta:
        bits.append(f"尺寸 {meta['width']}×{meta['height']}")
    if "date" in meta:
        bits.append(f"拍摄 {meta['date']}")
    camera = " ".join(filter(None, [meta.get("make"), meta.get("model")]))
    if camera:
        bits.append(f"相机 {camera}")
    if "pages" in meta:
        bits.append(f"页数 {meta['pages']}")
    if "slides" in meta:
        bits.append(f"幻灯片 {meta['slides']}")
    if "sheets" in meta:
        bits.append(f"工作表 {meta['sheets']}")
    if "title" in meta:
        bits.append(meta["title"])
    if "artist" in meta:
        bits.append(f"艺术家 {meta['artist']}")
    if "duration" in meta:
        bits.append(f"时长 {meta['duration']}")
    if "member_count" in meta:
        names = "、".join(meta.get("members", []))
        bits.append(f"包含 {meta['member_count']} 项" + (f"：{names}" if names else ""))
    return bits


def summarize(
    text: str | None,
    meta: dict | None = None,
    *,
    name: str = "",
) -> str | None:
    """生成可读概述；没有文字也没有元数据时返回 None。"""
    meta = meta or {}
    if not text and not meta:
        return None
    type_label = metadata.infer_type(Path(name).suffix.lower()) if name else "other"
    head = f"类型：{type_label if type_label != 'other' else '文件'}"
    kw = keywords(text, top_n=3)
    if kw:
        head += " · 关键词：" + "、".join(kw)
    lines = [head]
    if text:
        lines.append("概述：" + " ".join(text.split())[:60])
    bits = _meta_bits(meta)
    if bits:
        lines.append(" · ".join(bits))
    return "\n".join(lines)


def build_summaries(
    files: Iterable[ScannedFile],
    texts: dict[str, str | None],
    *,
    meta_fn: Callable = extract_metadata,
) -> list[tuple[str, str]]:
    """为一批文件生成概述，返回 [(绝对路径, 概述)]。"""
    results: list[tuple[str, str]] = []
    for f in files:
        summary = summarize(texts.get(str(f.path)), meta_fn(f.path), name=f.name)
        if summary:
            results.append((str(f.path), summary))
    return results
