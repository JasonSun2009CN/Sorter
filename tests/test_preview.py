# =============================================================================
# tests/test_preview.py —— 变更预览引擎（Phase 6 纯逻辑）
# =============================================================================

import sys

import pytest

from app.core.organizer import MovePlan
from app.core.preview import (
    CONFLICT_COLLISION,
    CONFLICT_MUTUAL,
    CONFLICT_OCCUPIED,
    generate_preview,
    _norm_path,
)


def _plan(root, name, target_dir="PDF", reason="PDF"):
    return MovePlan(
        source=root / name,
        target=root / target_dir / name,
        reason=reason,
    )


def _make(tmp_path, *names):
    """创建真实文件并返回路径。"""
    paths = []
    for name in names:
        p = tmp_path / name
        p.write_bytes(b"%PDF-" + name.encode())
        paths.append(p)
    return paths


def test_generate_preview_basic(tmp_path):
    p1 = _make(tmp_path, "a.pdf")[0]
    p2 = _make(tmp_path, "b.docx")[0]
    moves = [_plan(tmp_path, p1.name), _plan(tmp_path, p2.name, "DOCX", "DOCX")]
    report = generate_preview(moves)
    assert len(report.moves) == 2
    assert report.conflicts == []
    assert report.summary["total"] == 2
    assert report.summary["blocked_count"] == 0
    assert report.summary["by_reason"] == {"DOCX": 1, "PDF": 1}
    assert len(report.safe_moves) == 2


def test_generate_preview_empty():
    report = generate_preview([])
    assert report.summary["total"] == 0
    assert report.conflicts == []
    assert report.warnings == []
    assert report.safe_moves == []


def test_collision_same_target(tmp_path):
    # 不同子目录的同名文件映射到同一目标 → 同名目标冲突
    _make(tmp_path, "a.pdf")
    (tmp_path / "sub").mkdir()
    _make(tmp_path, "sub/a.pdf")
    source1 = tmp_path / "a.pdf"
    source2 = tmp_path / "sub" / "a.pdf"
    target = tmp_path / "PDF" / "a.pdf"
    moves = [
        MovePlan(source=source1, target=target, reason="PDF"),
        MovePlan(source=source2, target=target, reason="PDF"),
    ]
    report = generate_preview(moves)
    collisions = [c for c in report.conflicts if c.kind == CONFLICT_COLLISION]
    assert len(collisions) == 1
    assert len(collisions[0].moves) == 2
    assert report.blocked_sources == {source1, source2}
    assert report.safe_moves == []
    assert report.summary["blocked_count"] == 2


def test_collision_different_names_no_conflict(tmp_path):
    _make(tmp_path, "a.pdf", "b.pdf")
    moves = [_plan(tmp_path, "a.pdf"), _plan(tmp_path, "b.pdf")]
    report = generate_preview(moves)
    assert report.conflicts == []


def test_occupied_external(tmp_path):
    # 目标 PDF/a.pdf 已存在且不是待移动文件
    _make(tmp_path, "a.pdf")
    (tmp_path / "PDF").mkdir()
    (tmp_path / "PDF" / "a.pdf").write_bytes(b"%PDF-other")
    moves = [_plan(tmp_path, "a.pdf")]
    report = generate_preview(moves)
    occupied = [c for c in report.conflicts if c.kind == CONFLICT_OCCUPIED]
    assert len(occupied) == 1
    assert report.safe_moves == []


def test_target_dir_exists_file_absent_no_conflict(tmp_path):
    # 目录 PDF/ 已存在但文件不在 → 不误报
    _make(tmp_path, "a.pdf")
    (tmp_path / "PDF").mkdir()
    moves = [_plan(tmp_path, "a.pdf")]
    report = generate_preview(moves)
    assert report.conflicts == []
    assert len(report.safe_moves) == 1


def test_mutual_swap(tmp_path):
    # A→B 且 B→A：互换位置
    a = _make(tmp_path, "a.pdf")[0]
    b = _make(tmp_path, "b.pdf")[0]
    moves = [
        MovePlan(source=a, target=b, reason="swap"),
        MovePlan(source=b, target=a, reason="swap"),
    ]
    report = generate_preview(moves)
    mutual = [c for c in report.conflicts if c.kind == CONFLICT_MUTUAL]
    assert len(mutual) == 2
    assert report.safe_moves == []
    assert report.summary["blocked_count"] == 2


def test_duplicates_warning(tmp_path):
    # 两个内容相同的文件
    p1 = tmp_path / "copy1.txt"
    p2 = tmp_path / "copy2.txt"
    p1.write_text("same content", encoding="utf-8")
    p2.write_text("same content", encoding="utf-8")
    moves = [_plan(tmp_path, "copy1.txt", "TXT", "TXT"), _plan(tmp_path, "copy2.txt", "TXT", "TXT")]
    report = generate_preview(moves)
    assert any("重复" in w for w in report.warnings)
    assert report.summary["warning_count"] >= 1
    # 重复是警告不是冲突
    assert report.safe_moves == moves


def test_extra_warnings_appended(tmp_path):
    _make(tmp_path, "a.pdf")
    moves = [_plan(tmp_path, "a.pdf")]
    report = generate_preview(moves, extra_warnings=["低置信度标签：4 个文件"])
    assert report.warnings == ["低置信度标签：4 个文件"]
    assert report.summary["warning_count"] == 1


def test_sources_deleted_do_not_break(tmp_path):
    # 源文件已消失：预览不崩溃，重复检测跳过该文件
    p = tmp_path / "a.pdf"
    moves = [MovePlan(source=p, target=tmp_path / "PDF" / "a.pdf", reason="PDF")]
    report = generate_preview(moves)
    assert report.summary["total"] == 1
    assert not any("重复" in w for w in report.warnings)


@pytest.mark.skipif(sys.platform == "linux", reason="大小写不敏感仅在 macOS/Windows")
def test_casefold_collision(tmp_path):
    # 仅大小写不同的目标应判为碰撞（macOS 大小写不敏感）
    a = _make(tmp_path, "a.pdf")[0]
    b = _make(tmp_path, "b.pdf")[0]
    moves = [
        MovePlan(source=a, target=tmp_path / "PDF" / "a.pdf", reason="PDF"),
        MovePlan(source=b, target=tmp_path / "pdf" / "a.pdf", reason="PDF"),
    ]
    report = generate_preview(moves)
    assert any(c.kind == CONFLICT_COLLISION for c in report.conflicts)


def test_norm_path_casefold():
    p = "/tmp/Foo/Bar.pdf"
    normed = _norm_path(__import__("pathlib").Path(p))
    if sys.platform == "linux":
        assert "/tmp/Foo/Bar.pdf" in normed
    else:
        assert normed == normed.casefold()
