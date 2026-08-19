# =============================================================================
# app/database/models.py —— 表结构定义
#
# 作用：
#   集中定义 SQLite 表结构与索引，提供幂等建表入口。
#
# 表：
#   files              已索引文件及其元数据
#   tags               标签字典（system / learned / user）
#   file_tags          文件—标签关联（含置信度）
#   operations         组织操作记录（撤销用）
#   training_feedback  用户修正样本（个性化训练用）
#
# 大致结构：
#   SCHEMA: dict[str, str]  # 表名 → CREATE TABLE 语句
#   def create_tables(conn) # 幂等建表
# =============================================================================

"""SQLite 表结构与幂等建表入口。"""

from __future__ import annotations

import sqlite3

# 表名 → CREATE TABLE 语句
SCHEMA: dict[str, str] = {
    # 已索引的文件及其元数据（Phase 1 核心表）
    "files": """
        CREATE TABLE IF NOT EXISTS files (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            path         TEXT    NOT NULL UNIQUE,
            name         TEXT    NOT NULL,
            extension    TEXT    NOT NULL DEFAULT '',
            size         INTEGER NOT NULL DEFAULT 0,
            mtime        REAL    NOT NULL DEFAULT 0,
            ctime        REAL    NOT NULL DEFAULT 0,
            is_dir       INTEGER NOT NULL DEFAULT 0,
            content_hash TEXT,
            scanned_at   TEXT    NOT NULL
        )
    """,
    # 标签字典：system（确定性）/ learned（ML 预测）/ user（用户自建）
    "tags": """
        CREATE TABLE IF NOT EXISTS tags (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL DEFAULT 'system'  -- system | learned | user
        )
    """,
    # 文件—标签关联（含置信度与来源）
    "file_tags": """
        CREATE TABLE IF NOT EXISTS file_tags (
            file_id    INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            tag_id     INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
            confidence REAL    NOT NULL DEFAULT 0,
            source     TEXT    NOT NULL DEFAULT 'system',  -- system | learned | user
            PRIMARY KEY (file_id, tag_id, source)
        )
    """,
    # 组织操作记录（撤销用）
    "operations": """
        CREATE TABLE IF NOT EXISTS operations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp  TEXT NOT NULL,
            moves_json TEXT NOT NULL,  -- [{"old": "...", "new": "..."}, ...]
            undone     INTEGER NOT NULL DEFAULT 0
        )
    """,
    # 用户修正样本（个性化训练用）
    "training_feedback": """
        CREATE TABLE IF NOT EXISTS training_feedback (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id    INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            tag_id     INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
            accepted   INTEGER NOT NULL DEFAULT 1,
            created_at TEXT    NOT NULL
        )
    """,
}

# 建表后补充的常用索引（同样幂等）
_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension)",
    "CREATE INDEX IF NOT EXISTS idx_files_size      ON files(size)",
    "CREATE INDEX IF NOT EXISTS idx_file_tags_tag   ON file_tags(tag_id)",
    "CREATE INDEX IF NOT EXISTS idx_operations_undone ON operations(undone)",
]


def create_tables(conn: sqlite3.Connection) -> None:
    """在给定连接上幂等创建全部表与索引。"""
    for ddl in SCHEMA.values():
        conn.execute(ddl)
    for ddl in _INDEXES:
        conn.execute(ddl)
    conn.commit()
