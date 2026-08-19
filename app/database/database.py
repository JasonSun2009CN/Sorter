# =============================================================================
# app/database/database.py —— SQLite 访问层
#
# 作用：
#   封装数据库连接生命周期与通用 CRUD，供 core / ml / gui 各层调用。
#   耗时的写操作应交给工作线程，避免阻塞界面。
#
# 大致结构：
#   class Database
#       __init__(path) / connect() / close()
#       execute(sql, params)             # 通用执行
#       query(sql, params) -> rows       # 通用查询
#       insert_file(...) / get_file(...) # 业务 CRUD
#       transaction()                    # 事务上下文
# =============================================================================

"""SQLite 连接管理与通用 CRUD。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from app.database.models import create_tables


def _now() -> str:
    """返回当前时间的 ISO 字符串（本地时间，精确到秒）。"""
    return datetime.now().isoformat(timespec="seconds")


class Database:
    """封装 SQLite 连接生命周期与常用读写操作。"""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._conn: sqlite3.Connection | None = None

    # ---- 连接管理 ----

    @property
    def conn(self) -> sqlite3.Connection:
        """惰性打开连接。"""
        conn = self._conn
        if conn is None:
            conn = self._connect()
            self._conn = conn
        return conn

    def _connect(self) -> sqlite3.Connection:
        """建立新连接并设置行工厂 / 外键 / WAL。"""
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close(self) -> None:
        """关闭连接（幂等）。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---- 建表 / 通用读写 ----

    def initialize(self) -> None:
        """幂等创建全部表结构。"""
        create_tables(self.conn)

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行一条写语句并立即提交。"""
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """执行查询并返回全部行（sqlite3.Row，支持 dict 式取值）。"""
        cur = self.conn.execute(sql, params)
        return list(cur.fetchall())

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """事务上下文：块内未抛出异常则提交，否则回滚。"""
        conn = self.conn
        try:
            conn.execute("BEGIN")
            yield conn
        except BaseException:
            conn.rollback()
            raise
        else:
            conn.commit()

    # ---- Phase 1 业务 CRUD：files ----

    def insert_file(
        self,
        *,
        path: str,
        name: str,
        extension: str,
        size: int,
        mtime: float,
        ctime: float,
        is_dir: bool = False,
        content_hash: str | None = None,
    ) -> int:
        """写入一条文件索引；若 path 已存在则更新该行。返回记录 id。"""
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT id FROM files WHERE path = ?", (path,)
            ).fetchone()
            if row is not None:
                conn.execute(
                    """
                    UPDATE files
                       SET name = ?, extension = ?, size = ?, mtime = ?, ctime = ?,
                           is_dir = ?, content_hash = ?, scanned_at = ?
                     WHERE id = ?
                    """,
                    (
                        name, extension, size, mtime, ctime,
                        int(is_dir), content_hash, _now(), row["id"],
                    ),
                )
                return row["id"]
            cur = conn.execute(
                """
                INSERT INTO files
                       (path, name, extension, size, mtime, ctime,
                        is_dir, content_hash, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    path, name, extension, size, mtime, ctime,
                    int(is_dir), content_hash, _now(),
                ),
            )
            rid = cur.lastrowid
            return rid if rid is not None else 0

    def get_file_by_path(self, path: str) -> sqlite3.Row | None:
        """按绝对路径查询一条文件索引。"""
        rows = self.query("SELECT * FROM files WHERE path = ?", (path,))
        return rows[0] if rows else None

    def get_all_files(self) -> list[sqlite3.Row]:
        """返回全部文件索引（按路径排序）。"""
        return self.query("SELECT * FROM files ORDER BY path")
