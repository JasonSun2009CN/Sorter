# =============================================================================
# app/ml/training.py —— 训练数据与个性化学习
#
# 作用：
#   保存用户对标签的修正，作为个性化训练数据；支持用这些数据
#   对分类器进行增量 / 重新训练，使预测逐渐贴合用户习惯。
#
# 结构：
#   save_correction(db, file_id, tag, accepted)  # 写入反馈表（同对覆盖）
#   load_training_data(db) -> [(file, tags), ...]# 读取已确认样本（按文件聚合）
#   retrain(classifier, X, y)                    # 个性化再训练
# =============================================================================

"""训练数据管理：用户修正样本的读写与再训练入口。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.scanner import ScannedFile

if TYPE_CHECKING:
    from app.database import Database


def _now() -> str:
    """当前时间 ISO 字符串（本地时间，精确到秒）。"""
    return datetime.now().isoformat(timespec="seconds")


def _ensure_tag(conn, name: str, kind: str = "user") -> int:
    """确保标签存在并返回其 id（幂等）。"""
    conn.execute("INSERT OR IGNORE INTO tags (name, kind) VALUES (?, ?)", (name, kind))
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    return row["id"] if row else 0


def save_correction(
    db: "Database",
    file_id: int,
    tag: str,
    accepted: bool = True,
    kind: str = "user",
) -> None:
    """记录用户对 (文件, 标签) 的修正；同一对重复保存时覆盖旧值。"""
    with db.transaction() as conn:
        tag_id = _ensure_tag(conn, tag, kind)
        conn.execute(
            "DELETE FROM training_feedback WHERE file_id = ? AND tag_id = ?",
            (file_id, tag_id),
        )
        conn.execute(
            "INSERT INTO training_feedback (file_id, tag_id, accepted, created_at) "
            "VALUES (?, ?, ?, ?)",
            (file_id, tag_id, int(accepted), _now()),
        )


def load_training_data(db: "Database") -> list[tuple[ScannedFile, set[str]]]:
    """读取所有已接受的修正样本，按文件聚合成 [(文件, 标签集合)]。

    文件直接从 files 表重建 ``ScannedFile``，不重新 stat 磁盘，
    因此即使源文件已移动 / 删除也能安全加载。
    """
    rows = db.query(
        """
        SELECT f.path, f.size, f.mtime, f.ctime, t.name AS tag
          FROM training_feedback tf
          JOIN files f ON f.id = tf.file_id
          JOIN tags  t ON t.id = tf.tag_id
         WHERE tf.accepted = 1
         ORDER BY f.path
        """
    )
    groups: dict[str, dict] = {}
    for row in rows:
        group = groups.setdefault(
            row["path"],
            {
                "file": ScannedFile(
                    path=Path(row["path"]),
                    size=row["size"],
                    mtime=row["mtime"],
                    ctime=row["ctime"],
                ),
                "tags": set(),
            },
        )
        group["tags"].add(row["tag"])
    return [(g["file"], g["tags"]) for g in groups.values()]


def retrain(classifier, X, y) -> object:
    """用给定数据重新训练分类器（当前为全量重训，后续可做增量更新）。"""
    return classifier.train(X, y)
