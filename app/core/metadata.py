# =============================================================================
# app/core/metadata.py —— 元数据提取
#
# 作用：
#   在基本文件信息之上，提取更结构化的元数据：
#   文档类型推断、重复检测、目录归属等，供标签系统使用。
#
# 大致结构：
#   def get_basic_metadata(path) -> dict       # 大小、时间、扩展名等
#   def detect_duplicates(files) -> list[set]  # 按大小 + 哈希聚类重复文件
#   def infer_type(extension) -> str           # pdf / image / archive ...
#   def is_recently_modified(mtime) -> bool    # 判定 recently-modified 标签
# =============================================================================

"""元数据提取：基本信息、类型推断、重复检测等确定性标签辅助。"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.core.scanner import ScannedFile

# 常见扩展名 → 类别
EXTENSION_TYPES: dict[str, str] = {
    # 文档
    ".pdf": "pdf",
    ".doc": "docx", ".docx": "docx", ".rtf": "docx", ".odt": "docx", ".pages": "docx",
    # 表格
    ".xls": "spreadsheet", ".xlsx": "spreadsheet", ".ods": "spreadsheet", ".csv": "spreadsheet",
    # 演示
    ".ppt": "presentation", ".pptx": "presentation", ".key": "presentation", ".odp": "presentation",
    # 图片
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image",
    ".webp": "image", ".bmp": "image", ".tiff": "image", ".tif": "image",
    ".svg": "image", ".heic": "image", ".jfif": "image",
    # 压缩包
    ".zip": "archive", ".tar": "archive", ".gz": "archive", ".tgz": "archive",
    ".bz2": "archive", ".xz": "archive", ".7z": "archive", ".rar": "archive",
    # 音视频
    ".mp4": "video", ".mov": "video", ".avi": "video", ".mkv": "video", ".webm": "video",
    ".mp3": "audio", ".wav": "audio", ".flac": "audio", ".aac": "audio",
    ".m4a": "audio", ".ogg": "audio",
    # 纯文本
    ".txt": "text", ".md": "text", ".markdown": "text", ".rst": "text",
}


def get_basic_metadata(path: str | Path) -> dict:
    """返回文件的名称 / 扩展名 / 大小 / 时间戳等基本信息。"""
    p = Path(path)
    st = p.stat()
    return {
        "path": str(p),
        "name": p.name,
        "extension": p.suffix.lower(),
        "size": st.st_size,
        "mtime": st.st_mtime,
        "ctime": st.st_ctime,
    }


def content_hash(path: str | Path, algo: str = "md5", chunk_size: int = 1 << 20) -> str | None:
    """分块计算文件内容哈希；读取失败（无权限 / 目录等）返回 None。"""
    digest = hashlib.new(algo)
    try:
        with open(path, "rb") as fh:
            while chunk := fh.read(chunk_size):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def infer_type(extension: str) -> str:
    """按扩展名推断文件类别；未收录的扩展名返回 other。"""
    ext = extension.lower()
    if not ext.startswith("."):
        ext = "." + ext
    return EXTENSION_TYPES.get(ext, "other")


def detect_duplicates(files: Iterable[ScannedFile]) -> list[list[ScannedFile]]:
    """找出内容重复的文件组（每组 ≥2 个）。

    先按 size 粗分组，size 相同的再按内容哈希聚类，减少全量哈希计算。
    """
    by_size: dict[int, list[ScannedFile]] = {}
    for f in files:
        by_size.setdefault(f.size, []).append(f)

    by_hash: dict[str, list[ScannedFile]] = {}
    for group in by_size.values():
        if len(group) < 2:
            continue  # 大小唯一，不可能重复
        for f in group:
            digest = content_hash(f.path)
            if digest is None:
                continue
            by_hash.setdefault(digest, []).append(f)

    return [group for group in by_hash.values() if len(group) >= 2]


def is_recently_modified(mtime: float, days: int = 30) -> bool:
    """判断 mtime 是否在最近 days 天内（供 recently-modified 系统标签使用）。"""
    cutoff = datetime.now().timestamp() - days * 86_400
    return mtime >= cutoff
