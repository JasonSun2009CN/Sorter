# =============================================================================
# tests/test_autoplan.py —— 自动规划整理
# =============================================================================

from pathlib import Path

from app.core.autoplan import _best_tag, auto_plan
from app.core.organizer import MovePlan
from app.core.preview import CONFLICT_COLLISION, generate_preview
from app.core.scanner import Scanner, ScannedFile
from app.core.tagging import assign_system_tags
from app.database import Database
from app.database.queries import add_user_tag


def _setup(tmp_path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "b.pdf").write_bytes(b"%PDF")
    (tmp_path / "c.xyz").write_bytes(b"blob")  # 类型 other，无标签
    db = Database(tmp_path / "index.db")
    db.initialize()
    files = Scanner(db).scan(tmp_path, db_path=db.path)
    Scanner(db).index_in_db(db, files)
    assign_system_tags(db, files)
    return db, files


def _file_id(db, name):
    return db.query("SELECT id FROM files WHERE name = ?", (name,))[0]["id"]


def _file_id_by_path(db, rel):
    return db.query("SELECT id FROM files WHERE path = ?", (str(rel),))[0]["id"]


def _add_tag(db, file_id, name, kind="learned", source="learned", confidence=0.8):
    with db.transaction() as conn:
        conn.execute("INSERT OR IGNORE INTO tags (name, kind) VALUES (?, ?)", (name, kind))
        tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO file_tags (file_id, tag_id, confidence, source) "
            "VALUES (?, ?, ?, ?)",
            (file_id, tag_id, confidence, source),
        )


def _plan_for(plans, name):
    return next(p for p in plans if p.source.name == name)


def test_priority_user_over_learned(tmp_path):
    db, files = _setup(tmp_path)
    fid = _file_id(db, "a.txt")
    add_user_tag(db, fid, "重要")          # source='user'
    _add_tag(db, fid, "school")            # source='learned'
    plans = auto_plan(db, files, tmp_path)
    assert _plan_for(plans, "a.txt").target == tmp_path / "重要" / "a.txt"


def test_priority_learned_over_type(tmp_path):
    db, files = _setup(tmp_path)
    _add_tag(db, _file_id(db, "b.pdf"), "report")
    plans = auto_plan(db, files, tmp_path)
    assert _plan_for(plans, "b.pdf").target == tmp_path / "report" / "b.pdf"


def test_only_system_falls_back_to_type(tmp_path):
    db, files = _setup(tmp_path)
    plans = auto_plan(db, files, tmp_path)
    assert _plan_for(plans, "a.txt").target == tmp_path / "text" / "a.txt"
    assert _plan_for(plans, "b.pdf").target == tmp_path / "pdf" / "b.pdf"


def test_type_other_skipped(tmp_path):
    db, files = _setup(tmp_path)
    plans = auto_plan(db, files, tmp_path)
    assert all(p.source.name != "c.xyz" for p in plans)


def test_segment_sanitized(tmp_path):
    db, files = _setup(tmp_path)
    add_user_tag(db, _file_id(db, "a.txt"), "a/b:c")
    plans = auto_plan(db, files, tmp_path)
    assert _plan_for(plans, "a.txt").target == tmp_path / "a_b_c" / "a.txt"


def test_already_in_place_skipped(tmp_path):
    (tmp_path / "重要").mkdir()
    (tmp_path / "重要" / "x.txt").write_text("x", encoding="utf-8")
    db = Database(tmp_path / "index.db")
    db.initialize()
    files = Scanner(db).scan(tmp_path, db_path=db.path)
    Scanner(db).index_in_db(db, files)
    fid = _file_id(db, "x.txt")
    add_user_tag(db, fid, "重要")
    plans = auto_plan(db, files, tmp_path)
    assert all(p.source.name != "x.txt" for p in plans)


def test_same_filename_collision_surfaces(tmp_path):
    # 两个不同子目录的同名文件 → 同一最佳标签 → 同一目标 → 冲突
    (tmp_path / "s1").mkdir()
    (tmp_path / "s2").mkdir()
    (tmp_path / "s1" / "doc.txt").write_text("x", encoding="utf-8")
    (tmp_path / "s2" / "doc.txt").write_text("y", encoding="utf-8")
    db = Database(tmp_path / "index.db")
    db.initialize()
    files = Scanner(db).scan(tmp_path, db_path=db.path)
    Scanner(db).index_in_db(db, files)
    for rel in ("s1/doc.txt", "s2/doc.txt"):
        add_user_tag(db, _file_id_by_path(db, tmp_path / rel), "重要")
    plans = auto_plan(db, files, tmp_path)
    report = generate_preview(plans)
    assert any(c.kind == CONFLICT_COLLISION for c in report.conflicts)


def test_best_tag_matches():
    f = ScannedFile(path=Path("/tmp/a.txt"), size=1, mtime=0.0, ctime=0.0)
    assert _best_tag(f, [("text", "system", 1.0), ("school", "learned", 0.8)]) == "school"
    assert _best_tag(f, [("text", "system", 1.0), ("重要", "user", 1.0)]) == "重要"
    assert _best_tag(f, [("text", "system", 1.0)]) == "text"  # 类型兜底
    assert _best_tag(f, []) == "text"  # 无标签也按类型兜底
    f2 = ScannedFile(path=Path("/tmp/a.xyz"), size=1, mtime=0.0, ctime=0.0)
    assert _best_tag(f2, []) is None  # other → 跳过


def test_moveplans_are_sorted_and_moveplan(tmp_path):
    db, files = _setup(tmp_path)
    plans = auto_plan(db, files, tmp_path)
    assert isinstance(plans[0], MovePlan)
    sources = [str(p.source) for p in plans]
    assert sources == sorted(sources)
