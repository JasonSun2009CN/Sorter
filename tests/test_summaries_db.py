# =============================================================================
# tests/test_summaries_db.py —— 文件概述持久化
# =============================================================================

from app.database import Database
from app.database.summaries import get_summary, save_summaries


def test_save_and_get_roundtrip(tmp_path):
    db = Database(tmp_path / "index.db")
    db.initialize()
    fid = db.insert_file(
        path=str(tmp_path / "a.txt"), name="a.txt", extension=".txt",
        size=1, mtime=0.0, ctime=0.0,
    )
    n = save_summaries(db, [(str(tmp_path / "a.txt"), "类型：text · 关键词：alpha")])
    assert n == 1
    assert get_summary(db, fid) == "类型：text · 关键词：alpha"


def test_save_updates_existing(tmp_path):
    db = Database(tmp_path / "index.db")
    db.initialize()
    fid = db.insert_file(
        path=str(tmp_path / "a.txt"), name="a.txt", extension=".txt",
        size=1, mtime=0.0, ctime=0.0,
    )
    save_summaries(db, [(str(tmp_path / "a.txt"), "旧概述")])
    save_summaries(db, [(str(tmp_path / "a.txt"), "新概述")])
    assert get_summary(db, fid) == "新概述"
    rows = db.query("SELECT COUNT(*) AS n FROM file_summaries")
    assert rows[0]["n"] == 1  # upsert，不新增行


def test_get_summary_missing(tmp_path):
    db = Database(tmp_path / "index.db")
    db.initialize()
    fid = db.insert_file(
        path=str(tmp_path / "a.txt"), name="a.txt", extension=".txt",
        size=1, mtime=0.0, ctime=0.0,
    )
    assert get_summary(db, fid) is None


def test_old_db_gets_new_table(tmp_path):
    """旧库（无 file_summaries 表）initialize 后自动建表，无需 ALTER。"""
    db = Database(tmp_path / "index.db")
    db.initialize()
    # 模拟旧库：删除新表再重建连接
    db.execute("DROP TABLE IF EXISTS file_summaries")
    db.initialize()
    fid = db.insert_file(
        path=str(tmp_path / "a.txt"), name="a.txt", extension=".txt",
        size=1, mtime=0.0, ctime=0.0,
    )
    assert save_summaries(db, [(str(tmp_path / "a.txt"), "概述")]) == 1
    assert get_summary(db, fid) == "概述"
