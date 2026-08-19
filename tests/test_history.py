# =============================================================================
# tests/test_history.py —— 操作历史与撤销（Phase 7）
# =============================================================================

from app.core.history import (
    has_undoable,
    list_history,
    record_operation,
    undo_last,
)
from app.core.organizer import apply_plan
from app.database import Database


def _db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def _moves(tmp_path, names=("a.txt", "b.txt")):
    """把两个文件移到 TXT/ 下，返回 (old, new) 对。"""
    for name in names:
        (tmp_path / name).write_text(name, encoding="utf-8")
    from app.core.organizer import MovePlan

    plans = [
        MovePlan(source=tmp_path / name, target=tmp_path / "TXT" / name, reason="TXT")
        for name in names
    ]
    moved, errors = apply_plan(plans)
    assert not errors
    return moved


def test_record_and_undo_restores(tmp_path):
    db = _db(tmp_path)
    moved = _moves(tmp_path)
    assert (tmp_path / "TXT" / "a.txt").exists()
    record = record_operation(db, moved)
    assert record.id > 0
    assert record.undone is False

    undone, errors = undo_last(db)
    assert errors == []
    assert undone is not None
    assert undone.id == record.id
    assert undone.undone is True
    # 文件恢复原位置，目标目录不再有
    assert (tmp_path / "a.txt").exists()
    assert not (tmp_path / "TXT" / "a.txt").exists()
    # 记录已标记撤销
    rows = db.query("SELECT undone FROM operations WHERE id = ?", (record.id,))
    assert rows[0]["undone"] == 1
    # 二次撤销 → 无可撤销
    assert undo_last(db) == (None, [])


def test_list_history_order(tmp_path):
    db = _db(tmp_path)
    m1 = _moves(tmp_path, ("a.txt",))
    r1 = record_operation(db, m1)
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    from app.core.organizer import MovePlan

    m2 = apply_plan([MovePlan(source=tmp_path / "b.txt", target=tmp_path / "TXT" / "b.txt", reason="TXT")])
    assert not m2[1]
    r2 = record_operation(db, m2[0])
    hist = list_history(db)
    assert [h.id for h in hist] == [r2.id, r1.id]  # 最新在前
    assert hist[0].moves == [(str(tmp_path / "b.txt"), str(tmp_path / "TXT" / "b.txt"))]


def test_undo_empty_db(tmp_path):
    db = _db(tmp_path)
    assert undo_last(db) == (None, [])
    assert has_undoable(db) is False


def test_undo_partial_failure_still_marks(tmp_path):
    db = _db(tmp_path)
    moved = _moves(tmp_path)
    record_operation(db, moved)
    (tmp_path / "TXT" / "b.txt").unlink()  # 模拟 b 已被用户删除

    undone, errors = undo_last(db)
    assert len(errors) == 1
    assert undone is not None and undone.undone is True  # 仍标记撤销
    assert (tmp_path / "a.txt").exists()  # a 恢复
    assert not (tmp_path / "TXT" / "a.txt").exists()
    assert has_undoable(db) is False  # 不阻塞更早操作的撤销


def test_undo_occupied_original_refuses_overwrite(tmp_path):
    db = _db(tmp_path)
    moved = _moves(tmp_path)
    record_operation(db, moved)
    # 在 a 的原始位置放入另一个文件 → 撤销 a 时拒绝覆盖
    (tmp_path / "a.txt").write_text("other content", encoding="utf-8")

    undone, errors = undo_last(db)
    assert any("拒绝覆盖" in e for e in errors)
    assert undone is not None and undone.undone is True
    assert (tmp_path / "TXT" / "b.txt").exists() is False  # b 仍被恢复
