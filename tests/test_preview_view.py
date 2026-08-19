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


def _leaves(view):
    """收集文件树的所有叶子（文件名）与红字叶子。"""
    names, red = [], []
    def walk(item):
        for i in range(item.childCount()):
            child = item.child(i)
            if child.childCount() == 0:
                names.append(child.text(0))
                if child.foreground(0).color().name().casefold() == DANGER.casefold():
                    red.append(child.text(0))
            else:
                walk(child)
    root = view._tree.invisibleRootItem()
    for i in range(root.childCount()):
        walk(root.child(i))
    return names, red


def test_load_preview_renders_rows(qapp, tmp_path):
    view = PreviewView()
    report = _report(tmp_path)
    view.load_preview(report, root=tmp_path)
    assert view._tree.topLevelItemCount() == 1
    assert view._tree.topLevelItem(0).text(0) == "PDF"  # 目录节点
    names, red = _leaves(view)
    assert names == ["a.pdf", "b.pdf"]
    assert red == []
    assert "将移动 2 个文件" in view._summary.text()
    assert view._empty_hint.isHidden()
    view.deleteLater()


def test_conflict_rows_marked_red(qapp, tmp_path):
    view = PreviewView()
    report = _report(tmp_path, collide=True)
    view.load_preview(report, root=tmp_path)
    assert not view._conflicts_panel.isHidden()
    assert view._conflicts_list.count() == 1
    names, red = _leaves(view)
    assert names == ["a.pdf", "b.pdf"]
    assert red == ["a.pdf", "b.pdf"]  # 两个冲突文件都标红
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
    assert view._tree.isHidden()
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
    assert view._tree.isHidden()
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


# ---- 分类方式选择（自动整理） ----

def test_dimensions_changed_signal(qapp, tmp_path):
    view = PreviewView()
    fired = []
    view.dimensions_changed.connect(lambda dims: fired.append(list(dims)))
    # 默认 标签+类型；取消勾选「按类型」→ 只剩标签
    view._dim_checkboxes["type"].setChecked(False)
    assert fired and fired[-1] == ["tag"]
    # 勾选「按年份」→ [tag, year]（固定顺序）
    view._dim_checkboxes["year"].setChecked(True)
    assert fired[-1] == ["tag", "year"]
    view.deleteLater()


def test_show_dimensions_toggle(qapp, tmp_path):
    view = PreviewView()
    assert view._dim_row.isHidden() is False  # 默认可见
    view.show_dimensions(False)
    assert view._dim_row.isHidden()
    view.deleteLater()


def test_load_preview_syncs_dimensions_without_signal(qapp, tmp_path):
    view = PreviewView()
    fired = []
    view.dimensions_changed.connect(lambda dims: fired.append(dims))
    report = _report(tmp_path)
    view.load_preview(report, root=tmp_path, dimensions=["year", "extension"])
    assert view._dim_checkboxes["year"].isChecked()
    assert view._dim_checkboxes["extension"].isChecked()
    assert view._dim_checkboxes["tag"].isChecked() is False
    assert fired == []  # 同步勾选不触发重新生成
    view.deleteLater()
