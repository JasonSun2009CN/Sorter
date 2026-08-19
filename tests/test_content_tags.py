# =============================================================================
# tests/test_content_tags.py —— 内容关键词自动打标签
# =============================================================================

from app.core.extractor import extract_text
from app.core.scanner import Scanner
from app.core.tagging import assign_content_tags
from app.database import Database


def _setup(tmp_path):
    (tmp_path / "a.txt").write_text(
        "calculus derivative integral integral", encoding="utf-8"
    )
    (tmp_path / "b.pdf").write_bytes(b"%PDF")  # 无文本
    db = Database(tmp_path / "index.db")
    db.initialize()
    files = Scanner(db).scan(tmp_path, db_path=db.path)
    Scanner(db).index_in_db(db, files)
    return db, files


def _texts(files):
    return {str(f.path): extract_text(f.path) for f in files}


def test_content_tags_written_with_confidence(tmp_path):
    db, files = _setup(tmp_path)
    n = assign_content_tags(db, files, texts=_texts(files))
    assert n > 0
    rows = db.query(
        "SELECT t.name AS name, ft.confidence AS confidence "
        "FROM file_tags ft JOIN tags t ON t.id = ft.tag_id "
        "WHERE ft.source = 'learned'"
    )
    assert rows
    for r in rows:
        assert 0.4 <= r["confidence"] <= 0.9
    names = {r["name"] for r in rows}
    assert "integral" in names  # a.txt 的高频关键词


def test_content_tags_skip_no_text_file(tmp_path):
    db, files = _setup(tmp_path)
    # b.pdf 无文本 → 不产生标签；只统计 a.txt
    n = assign_content_tags(db, files, texts=_texts(files))
    assert n <= 2  # 只有 a.txt 的 top2 关键词


def test_content_tags_skip_system_vocab(tmp_path):
    (tmp_path / "x.txt").write_text("pdf pdf pdf archive archive archive", encoding="utf-8")
    db = Database(tmp_path / "index.db")
    db.initialize()
    files = Scanner(db).scan(tmp_path, db_path=db.path)
    Scanner(db).index_in_db(db, files)
    n = assign_content_tags(db, files, texts=_texts(files))
    assert n == 0  # pdf/archive 都是系统词汇，全部跳过


def test_content_tags_idempotent(tmp_path):
    db, files = _setup(tmp_path)
    texts = _texts(files)
    assign_content_tags(db, files, texts=texts)
    assign_content_tags(db, files, texts=texts)  # 再跑一次不翻倍
    row = db.query("SELECT id FROM files WHERE name = 'a.txt'")[0]
    n = db.query(
        "SELECT COUNT(*) AS n FROM file_tags WHERE file_id = ? AND source = 'learned'",
        (row["id"],),
    )[0]["n"]
    assert n <= 2  # top_n=2，INSERT OR IGNORE 幂等
