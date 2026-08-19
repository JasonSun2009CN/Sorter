# =============================================================================
# app/core/history.py —— 操作历史与撤销（Phase 7）
#
# 作用：
#   每次组织操作生成一条可逆记录（旧路径 → 新路径）写入 operations 表，
#   支持撤销最近一次操作，尽量恢复文件原状（best-effort）。
#
# 撤销语义：
#   无论个别文件是否恢复成功，记录都标记为已撤销（undone=1）——否则该记录
#   会成为新的"最新未撤销"，永久阻塞更早操作的撤销。失败的恢复在 UI 提示。
#
# 结构：
#   @dataclass OperationRecord
#   def record_operation(db, moves) -> OperationRecord
#   def list_history(db) -> list[OperationRecord]
#   def undo_last(db) -> (OperationRecord | None, list[str])
#   def has_undoable(db) -> bool
# =============================================================================

"""操作历史：记录组织操作并支持撤销回滚。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.core.organizer import move_file
from app.database import Database


def _now() -> str:
    """当前时间 ISO 字符串（本地时间，精确到秒）。"""
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class OperationRecord:
    """一条可逆操作记录。"""

    id: int
    timestamp: str
    moves: list[tuple[str, str]]  # (old, new)，绝对路径字符串
    undone: bool = False


def _row_to_record(row) -> OperationRecord:
    moves = [(m["old"], m["new"]) for m in json.loads(row["moves_json"])]
    return OperationRecord(
        id=row["id"],
        timestamp=row["timestamp"],
        moves=moves,
        undone=bool(row["undone"]),
    )


def record_operation(
    db: Database,
    moves: Iterable[tuple],
) -> OperationRecord:
    """写入一条可逆操作记录并返回。

    ``moves`` 必须非空；元素可为 (Path, Path) 或 (str, str)。
    ``moves_json`` 采用 ``[{"old": "...", "new": "..."}, ...]`` 结构。
    """
    pairs = [(str(old), str(new)) for old, new in moves]
    payload = json.dumps(
        [{"old": old, "new": new} for old, new in pairs], ensure_ascii=False
    )
    now = _now()
    cur = db.execute(
        "INSERT INTO operations (timestamp, moves_json, undone) VALUES (?, ?, 0)",
        (now, payload),
    )
    return OperationRecord(
        id=cur.lastrowid or 0, timestamp=now, moves=pairs, undone=False
    )


def list_history(db: Database) -> list[OperationRecord]:
    """读取全部操作记录，最新在前（id 降序）。"""
    rows = db.query(
        "SELECT id, timestamp, moves_json, undone FROM operations ORDER BY id DESC"
    )
    return [_row_to_record(r) for r in rows]


def undo_last(db: Database) -> tuple[OperationRecord | None, list[str]]:
    """回滚最近一次未撤销的操作（best-effort）。

    逐条反向移动 new→old；单个文件失败（已被移动 / 删除、原位置被占用等）
    收集错误，但**仍将记录标记为已撤销**，避免阻塞更早操作的撤销。
    返回 (记录, 错误列表)；无待撤销操作时返回 (None, [])。
    """
    rows = db.query(
        "SELECT id, timestamp, moves_json, undone FROM operations "
        "WHERE undone = 0 ORDER BY id DESC LIMIT 1"
    )
    if not rows:
        return None, []
    record = _row_to_record(rows[0])
    errors: list[str] = []
    for old, new in record.moves:
        try:
            move_file(Path(new), Path(old))
        except OSError as exc:
            errors.append(f"{Path(new).name}: {exc}")
    db.execute("UPDATE operations SET undone = 1 WHERE id = ?", (record.id,))
    record.undone = True
    return record, errors


def has_undoable(db: Database) -> bool:
    """是否存在尚未撤销的操作（菜单启用判断用）。"""
    return bool(db.query("SELECT 1 AS one FROM operations WHERE undone = 0 LIMIT 1"))
