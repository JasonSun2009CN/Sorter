# =============================================================================
# app/core/tagging.py —— 确定性系统标签（Phase 2）
#
# 作用：
#   基于确定性的文件元数据自动生成系统标签并写入数据库：
#   类型（pdf / image / archive ...）、大文件、最近修改、重复、所属目录。
#   不做任何 ML 预测，是 learned 标签的基础。
#
# 大致结构：
#   TAG_LARGE_FILE / TAG_RECENTLY_MODIFIED / TAG_DUPLICATE ...
#   def compute_system_tags(f, *, duplicate, ...) -> list[str]  # 纯计算
#   def assign_system_tags(db, files) -> int                    # 计算 + 写库
#   def _ensure_tag(conn, name, kind) -> int                    # 幂等写 tags
# =============================================================================

"""确定性系统标签的生成与持久化。"""

from __future__ import annotations

import sqlite3
from typing import Iterable

from app.core import metadata
from app.core.scanner import ScannedFile
from app.database import Database

# 系统标签名常量
TAG_LARGE_FILE = "large-file"
TAG_RECENTLY_MODIFIED = "recently-modified"
TAG_DUPLICATE = "duplicate"

# 判定阈值
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100 MiB
RECENT_DAYS = 30


def compute_system_tags(
    file: ScannedFile,
    *,
    duplicate: bool = False,
    large_threshold: int = LARGE_FILE_THRESHOLD,
    recent_days: int = RECENT_DAYS,
) -> list[str]:
    """为单个文件计算确定性系统标签（纯计算，不访问数据库）。"""
    tags: set[str] = set()

    # 类型标签（pdf / image / archive ...），other 不产生标签
    type_tag = metadata.infer_type(file.extension)
    if type_tag != "other":
        tags.add(type_tag)

    if file.size >= large_threshold:
        tags.add(TAG_LARGE_FILE)
    if metadata.is_recently_modified(file.mtime, recent_days):
        tags.add(TAG_RECENTLY_MODIFIED)
    if duplicate:
        tags.add(TAG_DUPLICATE)

    # 所属目录标签（直接父目录名）
    parent = file.path.parent.name
    if parent:
        tags.add(parent)

    return sorted(tags)


def _duplicate_paths(files: Iterable[ScannedFile]) -> set[str]:
    """返回所有属于重复组的文件绝对路径集合。"""
    dup_paths: set[str] = set()
    for group in metadata.detect_duplicates(files):
        for f in group:
            dup_paths.add(str(f.path))
    return dup_paths


def _ensure_tag(conn: sqlite3.Connection, name: str, kind: str = "system") -> int:
    """确保标签存在并返回其 id（幂等）。"""
    conn.execute(
        "INSERT OR IGNORE INTO tags (name, kind) VALUES (?, ?)", (name, kind)
    )
    row = conn.execute(
        "SELECT id FROM tags WHERE name = ?", (name,)
    ).fetchone()
    return row["id"] if row else 0


def assign_system_tags(
    db: Database,
    files: Iterable[ScannedFile],
    *,
    large_threshold: int = LARGE_FILE_THRESHOLD,
    recent_days: int = RECENT_DAYS,
) -> int:
    """为已索引文件计算系统标签并写入 tags / file_tags（单个事务）。

    返回写入的 file_tags 关联条数；未在数据库中索引到的文件会被跳过。
    """
    files = list(files)
    dup_paths = _duplicate_paths(files)
    written = 0
    with db.transaction() as conn:
        for f in files:
            row = conn.execute(
                "SELECT id FROM files WHERE path = ?", (str(f.path),)
            ).fetchone()
            if row is None:
                continue  # 未索引，跳过
            tags = compute_system_tags(
                f,
                duplicate=str(f.path) in dup_paths,
                large_threshold=large_threshold,
                recent_days=recent_days,
            )
            for tag in tags:
                tag_id = _ensure_tag(conn, tag, "system")
                conn.execute(
                    "INSERT OR IGNORE INTO file_tags "
                    "(file_id, tag_id, confidence, source) "
                    "VALUES (?, ?, ?, 'system')",
                    (row["id"], tag_id, 1.0),
                )
                written += 1
    return written
