# =============================================================================
# tests/test_gui_smoke.py —— GUI 冒烟测试（offscreen）
#
# 在 QT_QPA_PLATFORM=offscreen 下构造真实 MainWindow，验证视图装配、
# 文件加载、标签渲染与交互不抛异常。不依赖真实显示环境。
# =============================================================================

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.core.scanner import Scanner
from app.core.tagging import assign_system_tags
from app.database import Database
from app.database.queries import get_file_tags
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
        # 接受第一个标签后应重新渲染且不抛异常
        view._accept(file_id, tags[0]["tag"], tags[0]["source"])
        assert view._tags_layout.count() > 0
    finally:
        win.close()


def test_switch_view_through_workflow(qapp, env):
    db, files = env
    win = MainWindow(db)
    try:
        win._on_tagging_finished(files, n_system=5, n_learned=0)
        assert win.stack.currentIndex() == 1  # 标签审核
        win.tag_view.finished.emit()
        assert win.stack.currentIndex() == 2  # 规则占位页
    finally:
        win.close()
