# =============================================================================
# tests/test_gui_smoke.py —— GUI 冒烟测试（offscreen）
#
# 在 QT_QPA_PLATFORM=offscreen 下构造真实 MainWindow，验证视图装配、
# 文件加载、标签渲染、规则构建与工作流切换不抛异常。不依赖真实显示环境。
# =============================================================================

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.core.organizer import KIND_EXTENSION, KIND_TYPE, Rule, RuleLevel
from app.core.scanner import Scanner
from app.core.tagging import assign_system_tags
from app.database import Database
from app.database.queries import get_file_tags
from app.database.rules import get_last_rule, save_rule
from app.gui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def env(tmp_path, qapp):
    (tmp_path / "a.txt").write_text("alpha beta", encoding="utf-8")
    (tmp_path / "b.txt").write_text("gamma delta", encoding="utf-8")
    db = Database(tmp_path / "index.db")
    db.initialize()
    files = Scanner(db).scan(tmp_path, db_path=db.path)
    Scanner(db).index_in_db(db, files)
    assign_system_tags(db, files)
    return db, files


def test_main_window_assembles_four_views(qapp, env):
    db, _ = env
    win = MainWindow(db)
    try:
        assert win.stack.count() == 4
        assert win.stack.currentIndex() == 0  # 默认停在扫描视图
    finally:
        win.close()


def test_tag_view_load_and_render(qapp, env):
    db, files = env
    win = MainWindow(db)
    try:
        view = win.tag_view
        view.load_files(files)
        assert view._table.rowCount() == 2
        view._table.setCurrentCell(0, 0)
        assert view._header.text() != "选择左侧文件以查看标签"
        assert view._tags_layout.count() > 0  # 已渲染标签 chips
    finally:
        win.close()


def test_tag_view_accept_action(qapp, env):
    db, files = env
    win = MainWindow(db)
    try:
        view = win.tag_view
        view.load_files(files)
        view._table.setCurrentCell(0, 0)
        file_id = view._current_file_id()
        tags = get_file_tags(db, file_id)
        assert tags, "系统标签应存在"
        view._accept(file_id, tags[0]["tag"], tags[0]["source"])
        assert view._tags_layout.count() > 0
    finally:
        win.close()


def test_rules_view_preview_updates(qapp, env):
    db, files = env
    win = MainWindow(db)
    try:
        root = files[0].path.parent
        view = win.rules_view
        view.load_files(files, root)
        assert view._preview_list.count() == 1
        assert "规则为空" in view._preview_list.item(0).text()

        view.add_level(RuleLevel(KIND_EXTENSION))
        items = [view._preview_list.item(i).text() for i in range(view._preview_list.count())]
        assert "TXT — 2 个文件" in items
        assert not any("未匹配" in t for t in items)  # 两个 txt 全部匹配

        view.remove_level(0)
        assert view._preview_list.count() == 1
        assert "规则为空" in view._preview_list.item(0).text()
    finally:
        win.close()


def test_switch_view_through_workflow(qapp, env):
    db, files = env
    win = MainWindow(db)
    try:
        win._on_tagging_finished(files, n_system=5, n_learned=0)
        assert win.stack.currentIndex() == 1  # 标签审核
        win.tag_view.finished.emit()
        assert win.stack.currentIndex() == 2  # 组织规则
        win.rules_view.finished.emit()
        assert win.stack.currentIndex() == 3  # 变更预览
        assert get_last_rule(db) is None      # 空规则不保存
        assert win.preview_view._empty_hint.isHidden() is False  # 空规则 → 空态
    finally:
        win.close()


def test_rules_ready_saves_rule(qapp, env):
    db, files = env
    win = MainWindow(db)
    try:
        root = files[0].path.parent
        win.scan_view.set_folder(root)
        win._on_tagging_finished(files, n_system=5, n_learned=0)
        win.tag_view.finished.emit()  # → 规则视图载入文件
        win.rules_view.add_level(RuleLevel(KIND_EXTENSION))
        win.rules_view.finished.emit()  # → 保存规则 + 生成预览 + 切换
        assert win.stack.currentIndex() == 3
        last = get_last_rule(db)
        assert last is not None
        assert last[1].levels[0].kind == KIND_EXTENSION
        # 两个 txt 文件 → 预览表 2 行（TXT 目录，无冲突）
        assert win.preview_view._table.rowCount() == 2
        assert win.preview_view._conflicts_panel.isHidden()  # 无冲突
        assert "将移动 2 个文件" in win.preview_view._summary.text()
    finally:
        win.close()


def test_rules_view_auto_loads_last_rule(qapp, tmp_path):
    db = Database(tmp_path / "auto.db")
    db.initialize()
    save_rule(db, "默认规则", Rule([RuleLevel(KIND_TYPE)]))
    from app.gui.rules_view import RulesView

    view = RulesView(db)
    assert len(view.current_rule().levels) == 1
    assert view.current_rule().levels[0].kind == KIND_TYPE
    view.deleteLater()
