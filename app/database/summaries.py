# =============================================================================
# app/database/summaries.py —— 文件内容概述持久化
#
# 作用：
#   把识别内容后生成的概述写入 file_summaries 表，供标签审核界面展示。
#
# 结构：
#   save_summaries(db, [(path, summary)]) -> int   # 单事务 upsert，返回写入数
#   get_summary(db, file_id) -> str | None
# =============================================================================

"""文件概述 CRUD：概述文本的保存与读取。"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from app.database import Database


def _now() -> str:
    """当前时间 ISO 字符串（本地时间，精确到秒）。"""
    return datetime.now().isoformat(timespec="seconds")


def save_summaries(db: Database, path_summaries: Iterable[tuple]) -> int:
    """按文件路径写入概述；同文件覆盖更新。返回写入条数。

    ``path_summaries`` 元素为 (绝对路径 str|Path, 概述 str)。
    """
    rows = db.query("SELECT id, path FROM files")
    file_id_by_path = {row["path"]: row["id"] for row in rows}
    now = _now()
    written = 0
    with db.transaction() as conn:
        for path, summary in path_summaries:
            file_id = file_id_by_path.get(str(path))
            if file_id is None:
                continue  # 未索引，跳过
            conn.execute(
                """
                INSERT INTO file_summaries (file_id, summary, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE
                SET summary = excluded.summary, updated_at = excluded.updated_at
                """,
                (file_id, str(summary), now),
            )
            written += 1
    return written


def get_summary(db: Database, file_id: int) -> str | None:
    """读取某文件的概述；无则返回 None。"""
    rows = db.query("SELECT summary FROM file_summaries WHERE file_id = ?", (file_id,))
    summary = rows[0]["summary"] if rows else None
    return summary or None
