# =============================================================================
# app/database/rules.py —— 组织规则持久化
#
# 作用：
#   把用户定义的 Rule 序列化为 JSON 存入 rules 表，支持按名称幂等保存、
#   读取 / 删除。序列化细节在 app.core.organizer（rule_to_dict/rule_from_dict），
#   本模块只做 JSON 与数据库之间的薄封装。
#
# 结构：
#   save_rule(db, name, rule) -> int     # 按 name upsert（同名覆盖）
#   get_rule(db, rule_id) -> (name, Rule) | None
#   load_rules(db) -> [(id, name, Rule)] # 按 updated_at 降序
#   get_last_rule(db) -> (name, Rule) | None
#   delete_rule(db, rule_id) -> None
# =============================================================================

"""组织规则 CRUD：规则名 + JSON 持久化。"""

from __future__ import annotations

import json
from datetime import datetime

from app.core.organizer import Rule, rule_from_dict, rule_to_dict
from app.database import Database


def _now() -> str:
    """当前时间 ISO 字符串（本地时间，精确到秒）。"""
    return datetime.now().isoformat(timespec="seconds")


def save_rule(db: Database, name: str, rule: Rule) -> int:
    """保存规则；同名规则按更新处理（幂等），返回记录 id。"""
    rule_json = json.dumps(rule_to_dict(rule), ensure_ascii=False)
    now = _now()
    with db.transaction() as conn:
        row = conn.execute(
            "SELECT id FROM rules WHERE name = ?", (name,)
        ).fetchone()
        if row is not None:
            conn.execute(
                "UPDATE rules SET rule_json = ?, updated_at = ? WHERE id = ?",
                (rule_json, now, row["id"]),
            )
            return row["id"]
        cur = conn.execute(
            "INSERT INTO rules (name, rule_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (name, rule_json, now, now),
        )
        rid = cur.lastrowid
        return rid if rid is not None else 0


def _row_to_rule(row) -> tuple[str, Rule] | None:
    """把一行 rules 记录解析成 (name, Rule)。"""
    if row is None:
        return None
    return row["name"], rule_from_dict(json.loads(row["rule_json"]))


def get_rule(db: Database, rule_id: int) -> tuple[str, Rule] | None:
    """按 id 读取规则。"""
    rows = db.query("SELECT * FROM rules WHERE id = ?", (rule_id,))
    return _row_to_rule(rows[0]) if rows else None


def load_rules(db: Database) -> list[tuple[int, str, Rule]]:
    """读取全部规则，按最近更新降序（时间戳并列时按 id 降序）。"""
    rows = db.query("SELECT * FROM rules ORDER BY updated_at DESC, id DESC")
    return [
        (row["id"], row["name"], rule_from_dict(json.loads(row["rule_json"])))
        for row in rows
    ]


def get_last_rule(db: Database) -> tuple[str, Rule] | None:
    """读取最近更新的一条规则（用于启动时恢复）。"""
    rows = db.query("SELECT * FROM rules ORDER BY updated_at DESC, id DESC LIMIT 1")
    return _row_to_rule(rows[0]) if rows else None


def delete_rule(db: Database, rule_id: int) -> None:
    """按 id 删除规则。"""
    db.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
