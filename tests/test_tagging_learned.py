# =============================================================================
# tests/test_tagging_learned.py —— 学习标签端到端（Phase 3）
# =============================================================================

from app.core.scanner import Scanner
from app.core.tagging import assign_learned_tags
from app.database import Database
from app.ml import training


def _make_folder(tmp_path, files):
    for name, text in files:
        (tmp_path / name).write_text(text, encoding="utf-8")


def _scan_and_index(db, root):
    scanner = Scanner(db)
    files = scanner.scan(root, db_path=db.path)
    scanner.index_in_db(db, files)
    return files


def _label(db, files, labels_by_name):
    """按文件名给文件写入已接受修正样本，作为训练种子。"""
    for f in files:
        if f.name in labels_by_name:
            row = db.get_file_by_path(str(f.path))
            for tag in labels_by_name[f.name]:
                training.save_correction(db, row["id"], tag)


def test_assign_learned_tags_writes_predictions(tmp_path):
    # 两个主题，各 2 个文件，文本特征明显可分
    docs = [
        ("math_notes_1.txt", "calculus derivative integral limit"),
        ("math_notes_2.txt", "algebra equation polynomial quadratic"),
        ("physics_notes_1.txt", "force velocity acceleration momentum"),
        ("physics_notes_2.txt", "energy wave frequency wavelength"),
    ]
    _make_folder(tmp_path, docs)

    db = Database(tmp_path / "index.db")
    db.initialize()
    files = _scan_and_index(db, tmp_path)

    # 每个主题只标注 1 个文件，其余留给模型预测
    _label(db, files, {
        "math_notes_1.txt": {"math"},
        "physics_notes_1.txt": {"physics"},
    })

    written = assign_learned_tags(db, files, min_samples=2)
    assert written > 0

    rows = db.query(
        "SELECT ft.file_id, ft.tag_id, ft.confidence, ft.source, t.name "
        "FROM file_tags ft JOIN tags t ON t.id = ft.tag_id "
        "WHERE ft.source = 'learned'"
    )
    assert len(rows) >= 2
    assert all(0.0 < r["confidence"] <= 1.0 for r in rows)
    assert {r["name"] for r in rows} == {"math", "physics"}


def test_insufficient_training_data_returns_zero(tmp_path):
    # 只有 1 个已标注文件，不满足 min_samples=2
    docs = [("only.txt", "just one document"), ("other.txt", "another one")]
    _make_folder(tmp_path, docs)

    db = Database(tmp_path / "index.db")
    db.initialize()
    files = _scan_and_index(db, tmp_path)
    _label(db, files, {"only.txt": {"math"}})

    assert assign_learned_tags(db, files, min_samples=2) == 0
    rows = db.query("SELECT * FROM file_tags WHERE source = 'learned'")
    assert len(rows) == 0


def test_single_tag_kind_returns_zero(tmp_path):
    # 所有已标注文件只有同一个标签，分类器无法学习
    docs = [("a.txt", "alpha beta"), ("b.txt", "gamma delta")]
    _make_folder(tmp_path, docs)

    db = Database(tmp_path / "index.db")
    db.initialize()
    files = _scan_and_index(db, tmp_path)
    _label(db, files, {"a.txt": {"school"}, "b.txt": {"school"}})

    assert assign_learned_tags(db, files, min_samples=2) == 0
