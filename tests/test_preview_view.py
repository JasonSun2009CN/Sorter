# =============================================================================
# tests/test_preview_view.py —— 预览视图（offscreen）
# =============================================================================

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.core.organizer import MovePlan
from app.core.preview import generate_preview
from app.gui.preview_view import PreviewView
from app.gui.theme import DANGER


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _report(tmp_path, *, collide=False, occupy=False):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-a")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-b")
    source_a = tmp_path / "a.pdf"
    source_b = tmp_path / "b.pdf"
    if collide:
        target = tmp_path / "PDF" / "a.pdf"  # 两个都指向同一目标
        moves = [
            MovePlan(source=source_a, target=target, reason="PDF"),
            MovePlan(source=source_b, target=target, reason="PDF"),
        ]
    else:
        (tmp_path / "PDF").mkdir()
        moves = [
            MovePlan(source=source_a, target=tmp_path / "PDF" / "a.pdf", reason="PDF"),
            MovePlan(source=source_b, target=tmp_path / "PDF" / "b.pdf", reason="PDF"),
        ]
        if occupy:
            (tmp_path / "PDF" / "a.pdf").write_bytes(b"%PDF-other")  # 占用 a 的目标
    return generate_preview(moves)


def test_load_preview_renders_rows(qapp, tmp_path):
    view = PreviewView()
    report = _report(tmp_path)
    view.load_preview(report, root=tmp_path)
    assert view._table.rowCount() == 2
    assert "将移动 2 个文件" in view._summary.text()
    assert view._empty_hint.isHidden()
    view.deleteLater()


def test_conflict_rows_marked_red(qapp, tmp_path):
    view = PreviewView()
    report = _report(tmp_path, collide=True)
    view.load_preview(report, root=tmp_path)
    # 两行都应是冲突
    assert view._table.rowCount() == 2
    assert not view._conflicts_panel.isHidden()
    assert view._conflicts_list.count() == 1
    for row in range(view._table.rowCount()):
        status = view._table.item(row, 3)
        assert "冲突" in status.text()
        assert status.foreground().color().name().casefold() == DANGER.casefold()
    view.deleteLater()


def test_occupied_conflict_panel(qapp, tmp_path):
    view = PreviewView()
    report = _report(tmp_path, occupy=True)
    view.load_preview(report, root=tmp_path)
    assert not view._conflicts_panel.isHidden()
    assert view._conflicts_list.count() == 1
    assert "占用" in view._conflicts_list.item(0).text()
    view.deleteLater()


def test_warnings_panel(qapp, tmp_path):
    view = PreviewView()
    report = _report(tmp_path)
    report.warnings.append("低置信度标签：1 个文件")
    report.summary["warning_count"] += 1
    view.load_preview(report, root=tmp_path)
    assert not view._warnings_panel.isHidden()
    assert view._warnings_list.count() == 1
    view.deleteLater()


def test_empty_state(qapp, tmp_path):
    view = PreviewView()
    report = generate_preview([])
    view.load_preview(report, root=tmp_path)
    assert not view._empty_hint.isHidden()
    assert view._table.isHidden()
    assert "无需移动" in view._empty_hint.text()
    view.deleteLater()


def test_back_signal(qapp, tmp_path):
    view = PreviewView()
    fired = []
    view.back.connect(lambda: fired.append(True))
    view._back_btn.click()
    assert fired == [True]
    view.deleteLater()


def test_apply_button_disabled(qapp, tmp_path):
    view = PreviewView()
    assert view._apply_btn.isEnabled() is False  # Phase 7 前禁用
    view.deleteLater()


def test_clear_resets(qapp, tmp_path):
    view = PreviewView()
    report = _report(tmp_path)
    view.load_preview(report, root=tmp_path)
    view.clear()
    assert not view._empty_hint.isHidden()
    assert view._table.isHidden()
    view.deleteLater()


# ---- Phase 7：应用按钮 ----

def test_apply_button_enabled_when_safe_moves(qapp, tmp_path):
    view = PreviewView()
    report = _report(tmp_path)  # 无冲突 → 有 safe_moves
    view.load_preview(report, root=tmp_path)
    assert view._apply_btn.isEnabled() is True
    view.deleteLater()


def test_apply_button_disabled_when_all_blocked(qapp, tmp_path):
    view = PreviewView()
    report = _report(tmp_path, collide=True)  # 全冲突 → 无 safe_moves
    view.load_preview(report, root=tmp_path)
    assert view._apply_btn.isEnabled() is False
    view.deleteLater()


def test_apply_requested_signal(qapp, tmp_path):
    view = PreviewView()
    fired = []
    view.apply_requested.connect(lambda: fired.append(True))
    report = _report(tmp_path)
    view.load_preview(report, root=tmp_path)
    view._apply_btn.click()
    assert fired == [True]
    view.deleteLater()
