# =============================================================================
# app/core/scanner.py —— 文件扫描器
#
# 作用：
#   递归扫描用户选定的目录，收集每个文件的路径、扩展名、大小、时间戳等
#   基本信息，并写入 SQLite 索引。不读取内容、不做任何修改。
#
# 大致结构：
#   @dataclass ScannedFile
#       path / name / extension / size / mtime / ctime
#   class Scanner
#       scan(root) -> list[ScannedFile]   # 递归遍历目录
#       _is_ignored(path)                 # 过滤隐藏 / 系统文件
#       _index_in_db(files)               # 写入 database
# =============================================================================

"""递归扫描目录，收集文件基本信息并写入 SQLite 索引。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 仅类型检查，避免运行时循环依赖
    from app.database import Database


@dataclass
class ScannedFile:
    """扫描得到的一个文件条目（路径 + 一次 stat 捕获的基本信息）。"""

    path: Path
    size: int = 0
    mtime: float = 0.0
    ctime: float = 0.0
    is_dir: bool = False
    content_hash: str | None = None

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()

    @classmethod
    def from_path(cls, path: Path) -> "ScannedFile":
        """从路径一次性读取 stat 信息构造条目；stat 失败由调用方捕获。"""
        st = path.stat()
        return cls(
            path=path,
            size=st.st_size,
            mtime=st.st_mtime,
            ctime=st.st_ctime,
            is_dir=path.is_dir(),
        )


class Scanner:
    """递归文件扫描器。只读收集信息，绝不修改源文件。"""

    def __init__(self, db: "Database | None" = None) -> None:
        self.db = db

    @staticmethod
    def scan(
        root: str | Path,
        *,
        ignore_hidden: bool = True,
        db_path: str | Path | None = None,
    ) -> list[ScannedFile]:
        """递归扫描 root 目录下所有文件。

        - ignore_hidden=True 时跳过名称以 ``.`` 开头的文件与目录；
        - db_path 非空时跳过与数据库文件相同的路径（避免把自己索引进去）；
        - 不跟随目录符号链接；单个文件 stat 失败时静默跳过。
        """
        root = Path(root).expanduser().resolve()
        db_abs = Path(db_path).expanduser().resolve() if db_path else None

        files: list[ScannedFile] = []
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            if ignore_hidden:
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                filenames = [f for f in filenames if not f.startswith(".")]
            for filename in filenames:
                candidate = Path(dirpath) / filename
                if db_abs is not None and candidate.resolve() == db_abs:
                    continue
                try:
                    files.append(ScannedFile.from_path(candidate))
                except OSError:
                    continue  # 无权限 / 已删除等，跳过
        return files

    def index_in_db(self, db: "Database | None", files: list[ScannedFile]) -> int:
        """把扫描结果写入数据库（重复路径按更新处理）。返回写入条数。

        未显式传入 db 时回退到构造时传入的 self.db；两者都为空则报错。
        """
        db = db if db is not None else self.db
        if db is None:
            raise ValueError("index_in_db 需要一个 Database 实例")
        for f in files:
            db.insert_file(
                path=str(f.path),
                name=f.name,
                extension=f.extension,
                size=f.size,
                mtime=f.mtime,
                ctime=f.ctime,
                is_dir=f.is_dir,
                content_hash=f.content_hash,
            )
        return len(files)

    def scan_and_index(
        self,
        root: str | Path,
        db: "Database",
        **kwargs: object,
    ) -> list[ScannedFile]:
        """扫描并把结果写入数据库（数据库文件路径自动排除），返回扫描到的文件。"""
        files = self.scan(root, db_path=db.path, **kwargs)
        self.index_in_db(db, files)
        return files
