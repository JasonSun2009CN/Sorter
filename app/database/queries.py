# =============================================================================
# app/database/queries.py —— 标签读写辅助（不依赖 Qt，可单测）
#
# 作用：
#   为标签审核界面提供文件标签的读取与修改操作，数据库是唯一事实来源。
#   接受/拒绝语义（MVP）：
#     接受 = 写入 training_feedback(accepted=1)，保留 file_tags 行；
#     拒绝 = 写入 training_feedback(accepted=0)，并删除对应 file_tags 行
#            （标签从活跃列表消失，且不再被当作正例训练）。
#   删除 file_tags 一律按 source 过滤，避免误删同名系统标签。
#
# 结构：
#   get_file_tags(db, file_id) -> rows         # 读取某文件的活跃标签
#   set_tag_accepted(db, file_id, tag, *, source, accepted)
#   add_user_tag(db, file_id, tag)             # 用户新增标签
#   remove_user_tag(db, file_id, tag)          # 移除用户标签
# =============================================================================

"""标签读取与修改：文件 → 标签列表，以及接受 / 拒绝 / 增删。"""

from __future__ import annotations

import sqlite3

from app.ml.training import save_correction

from app.database import Database


def get_file_tags(db: Database, file_id: int) -> list[sqlite3.Row]:
    """返回某文件当前活跃的标签行（含来源、置信度、用户处理状态）。

    ``feedback`` 列为 None 表示用户尚未处理该标签；1 表示已接受。
    """
    return db.query(
        """
        SELECT t.id   AS tag_id,
               t.name AS tag,
               t.kind AS kind,
               ft.source     AS source,
               ft.confidence AS confidence,
               tf.accepted   AS feedback
          FROM file_tags ft
          JOIN tags t ON t.id = ft.tag_id
          LEFT JOIN training_feedback tf
                 ON tf.file_id = ft.file_id AND tf.tag_id = ft.tag_id
         WHERE ft.file_id = ?
         ORDER BY (t.kind = 'system') DESC, ft.confidence DESC, t.name
        """,
        (file_id,),
    )


def get_tags_by_path(db: Database) -> dict[str, set[str]]:
    """一次查询返回全库 文件路径 → 标签名集合（供规则规划批量使用，避免 N+1）。

    只包含当前活跃的 file_tags 行（被拒绝的标签行已删除）。
    """
    rows = db.query(
        """
        SELECT f.path AS path, t.name AS tag
          FROM files f
          JOIN file_tags ft ON ft.file_id = f.id
          JOIN tags  t      ON t.id = ft.tag_id
        """
    )
    result: dict[str, set[str]] = {}
    for row in rows:
        result.setdefault(row["path"], set()).add(row["tag"])
    return result


def _tag_id(db: Database, tag: str) -> int | None:
    """按名称查标签 id；不存在返回 None。"""
    rows = db.query("SELECT id FROM tags WHERE name = ?", (tag,))
    return rows[0]["id"] if rows else None


def set_tag_accepted(
    db: Database,
    file_id: int,
    tag: str,
    *,
    source: str,
    accepted: bool = True,
) -> None:
    """记录用户对预测标签的裁决。

    接受：写入 accepted=1 的反馈，保留 file_tags 行。
    拒绝：写入 accepted=0 的反馈，并删除该 (文件, 标签, source) 的 file_tags 行。
    """
    save_correction(db, file_id, tag, accepted=accepted, kind="user")
    if not accepted:
        tid = _tag_id(db, tag)
        if tid is not None:
            db.execute(
                "DELETE FROM file_tags "
                "WHERE file_id = ? AND tag_id = ? AND source = ?",
                (file_id, tid, source),
            )


def add_user_tag(db: Database, file_id: int, tag: str) -> None:
    """为用户文件手动添加标签：建 user 标签 + file_tags(source='user') + 反馈。"""
    save_correction(db, file_id, tag, accepted=True, kind="user")
    with db.transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO tags (name, kind) VALUES (?, 'user')", (tag,)
        )
        tag_id = conn.execute(
            "SELECT id FROM tags WHERE name = ?", (tag,)
        ).fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO file_tags "
            "(file_id, tag_id, confidence, source) VALUES (?, ?, 1.0, 'user')",
            (file_id, tag_id),
        )


def remove_user_tag(db: Database, file_id: int, tag: str) -> None:
    """移除用户手动添加的标签（只删 source='user' 的行，不影响同名系统/学习标签）。"""
    tid = _tag_id(db, tag)
    if tid is not None:
        db.execute(
            "DELETE FROM file_tags "
            "WHERE file_id = ? AND tag_id = ? AND source = 'user'",
            (file_id, tid),
        )
