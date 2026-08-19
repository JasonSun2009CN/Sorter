# =============================================================================
# tests/test_queries.py —— 标签读写辅助（Phase 4）
# =============================================================================

from app.core.scanner import Scanner
from app.core.tagging import assign_system_tags
from app.database import Database
from app.database import queries
from app.ml import training


def _setup(tmp_path):
    """建临时目录（2 个文本文件）+ 扫描建索引 + 打系统标签，返回 (db, files)。"""
    (tmp_path / "a.txt").write_text("alpha beta", encoding="utf-8")
    (tmp_path / "b.txt").write_text("gamma delta", encoding="utf-8")
    db = Database(tmp_path / "index.db")
    db.initialize()
    files = Scanner(db).scan(tmp_path, db_path=db.path)
    Scanner(db).index_in_db(db, files)
    assign_system_tags(db, files)
    return db, files


def _file_id(db, name):
    rows = db.query("SELECT id FROM files WHERE name = ?", (name,))
    assert rows, f"file {name} not indexed"
    return rows[0]["id"]


def test_get_file_tags_returns_system_rows(tmp_path):
    db, files = _setup(tmp_path)
    fid = _file_id(db, "a.txt")
    rows = queries.get_file_tags(db, fid)
    assert rows, "系统标签应已生成"
    # a.txt 至少应有 text（类型）与父目录标签
    assert all(r["source"] == "system" for r in rows)
    assert all(r["confidence"] == 1.0 for r in rows)
    assert all(r["feedback"] is None for r in rows)  # 尚未处理
    names = {r["tag"] for r in rows}
    assert "text" in names


def test_accept_keeps_row_and_writes_feedback(tmp_path):
    db, _ = _setup(tmp_path)
    fid = _file_id(db, "a.txt")
    tag = queries.get_file_tags(db, fid)[0]["tag"]

    queries.set_tag_accepted(db, fid, tag, source="system", accepted=True)

    rows = queries.get_file_tags(db, fid)
    assert any(r["tag"] == tag and r["feedback"] == 1 for r in rows)
    assert any(r["tag"] == tag for r in rows)  # 行仍在


def test_reject_removes_row_and_writes_negative_feedback(tmp_path):
    db, files = _setup(tmp_path)
    fid = _file_id(db, "a.txt")
    tag = queries.get_file_tags(db, fid)[0]["tag"]

    queries.set_tag_accepted(db, fid, tag, source="system", accepted=False)

    rows = queries.get_file_tags(db, fid)
    assert not any(r["tag"] == tag for r in rows)  # 从活跃列表消失
    # 负样本不会进入训练数据
    data = training.load_training_data(db)
    assert all(tag not in tags for _, tags in data)


def test_reject_only_removes_matching_source(tmp_path):
    """拒绝学习标签时，不应误删同名系统标签。"""
    db, files = _setup(tmp_path)
    fid = _file_id(db, "a.txt")
    # 伪造一条同名 learned 标签，验证删除只作用于指定 source
    with db.transaction() as conn:
        conn.execute("INSERT OR IGNORE INTO tags (name, kind) VALUES (?, ?)", ("text", "learned"))
        tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", ("text",)).fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO file_tags (file_id, tag_id, confidence, source) "
            "VALUES (?, ?, 0.8, 'learned')",
            (fid, tag_id),
        )

    queries.set_tag_accepted(db, fid, "text", source="learned", accepted=False)

    rows = queries.get_file_tags(db, fid)
    system = [r for r in rows if r["source"] == "system" and r["tag"] == "text"]
    learned = [r for r in rows if r["source"] == "learned" and r["tag"] == "text"]
    assert system, "同名系统标签应保留"
    assert not learned, "同名学习标签应被删除"


def test_add_and_remove_user_tag(tmp_path):
    db, _ = _setup(tmp_path)
    fid = _file_id(db, "a.txt")

    queries.add_user_tag(db, fid, "重要")

    rows = queries.get_file_tags(db, fid)
    assert any(r["tag"] == "重要" and r["source"] == "user" and r["feedback"] == 1 for r in rows)
    # 已接受样本进入训练数据
    data = training.load_training_data(db)
    assert any("重要" in tags for _, tags in data)

    queries.remove_user_tag(db, fid, "重要")
    rows = queries.get_file_tags(db, fid)
    assert not any(r["tag"] == "重要" for r in rows)
