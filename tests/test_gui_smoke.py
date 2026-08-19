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


# ---- Phase 7：应用变更 / 撤销 ----

def _drive_to_preview(win, files, monkeypatch):
    """驱动工作流到预览视图并返回根目录。"""
    root = files[0].path.parent
    win.scan_view.set_folder(root)
    win._on_tagging_finished(files, n_system=5, n_learned=0)
    win.tag_view.finished.emit()
    win.rules_view.add_level(RuleLevel(KIND_EXTENSION))
    win.rules_view.finished.emit()
    return root


def test_apply_undo_workflow(qapp, env, monkeypatch):
    db, files = env
    win = MainWindow(db)
    try:
        root = _drive_to_preview(win, files, monkeypatch)
        assert win.preview_view._apply_btn.isEnabled() is True

        # 同步执行 worker，避免真实线程
        monkeypatch.setattr(win, "_confirm_apply", lambda count: True)

        def fake_start_worker(worker, owner):
            worker.run()
            return None

        monkeypatch.setattr("app.gui.main_window.start_worker", fake_start_worker)

        win.preview_view._apply_btn.click()
        # 文件真的被移动到 TXT/
        assert (root / "TXT" / "a.txt").exists()
        assert (root / "TXT" / "b.txt").exists()
        assert not (root / "a.txt").exists()
        assert win.undo_action.isEnabled() is True
        assert win.preview_view._apply_btn.isEnabled() is False  # 消费预览
        assert "已移动 2 个文件" in win.statusBar().currentMessage()

        win.undo_action.trigger()
        # 文件回原处
        assert (root / "a.txt").exists()
        assert (root / "b.txt").exists()
        assert not (root / "TXT" / "a.txt").exists()
        assert win.undo_action.isEnabled() is False  # 无更多可撤销
        assert "已撤销" in win.statusBar().currentMessage()
    finally:
        win.close()


def test_apply_cancel_moves_nothing(qapp, env, monkeypatch):
    db, files = env
    win = MainWindow(db)
    try:
        root = _drive_to_preview(win, files, monkeypatch)
        monkeypatch.setattr(win, "_confirm_apply", lambda count: False)
        win.preview_view._apply_btn.click()
        # 确认被取消 → 不移动
        assert (root / "a.txt").exists()
        assert not (root / "TXT" / "a.txt").exists()
        assert win.undo_action.isEnabled() is False
        assert win.preview_view._apply_btn.isEnabled() is True  # 仍可重试
    finally:
        win.close()


# ---- 排版回归：重复渲染不残留（标签重叠 bug） ----

def test_tag_view_rerender_no_overlap(qapp, env):
    db, files = env
    win = MainWindow(db)
    try:
        view = win.tag_view
        view.load_files(files)
        view._table.setCurrentCell(0, 0)
        first = view._tags_layout.count()
        assert first > 0
        # 反复切换选择 → 每次重新渲染 chips
        view._table.setCurrentCell(1, 0)
        view._table.setCurrentCell(0, 0)
        view._table.setCurrentCell(1, 0)
        assert view._tags_layout.count() == first  # 无残留累积（旧 chip 不会重叠）
    finally:
        win.close()


def test_rules_view_rerender_no_overlap(qapp, env):
    db, files = env
    win = MainWindow(db)
    try:
        view = win.rules_view
        view.add_level(RuleLevel(KIND_TYPE))
        first = view._levels_layout.count()
        view.add_level(RuleLevel(KIND_EXTENSION))
        view.move_level(1, -1)
        view.remove_level(1)
        assert view._levels_layout.count() == first  # 结构操作后无残留
    finally:
        win.close()


# ---- 内容识别 / 自动规划 ----

def test_tag_view_shows_summary(qapp, env):
    db, files = env
    win = MainWindow(db)
    try:
        view = win.tag_view
        view.load_files(files)
        view._table.setCurrentCell(0, 0)
        assert view._summary_label.isHidden()  # 尚未生成概述

        from app.database.summaries import save_summaries
        fid = view._current_file_id()
        row = db.query("SELECT path FROM files WHERE id = ?", (fid,))[0]
        save_summaries(db, [(row["path"], "类型：text · 关键词：alpha")])
        # 切换选中触发刷新
        view._table.setCurrentCell(1, 0)
        view._table.setCurrentCell(0, 0)
        assert view._summary_label.isHidden() is False
        assert "关键词" in view._summary_label.text()
    finally:
        win.close()


def test_auto_plan_button_drives_preview(qapp, env):
    db, files = env
    win = MainWindow(db)
    try:
        root = files[0].path.parent
        win.scan_view.set_folder(root)
        win._on_tagging_finished(files, n_system=5, n_learned=0, n_content=4, n_summary=2)
        win.tag_view.finished.emit()
        # 「自动整理」按钮存在，点击 → 按类型自动规划 → 预览
        win.rules_view._auto_btn.click()
        assert win.stack.currentIndex() == 3
        assert win.preview_view._table.rowCount() >= 2  # 两个 txt 按类型
        assert win.preview_view._apply_btn.isEnabled() is True
    finally:
        win.close()


def test_auto_plan_then_apply_undo(qapp, env, monkeypatch):
    db, files = env
    win = MainWindow(db)
    try:
        root = files[0].path.parent
        win.scan_view.set_folder(root)
        win._on_tagging_finished(files, n_system=5, n_learned=0)
        win.tag_view.finished.emit()
        win.rules_view._auto_btn.click()  # 自动规划 → 预览

        monkeypatch.setattr(win, "_confirm_apply", lambda count: True)
        monkeypatch.setattr("app.gui.main_window.start_worker", lambda w, o: w.run())
        win.preview_view._apply_btn.click()
        assert (root / "text" / "a.txt").exists()  # 自动规划按类型移动
        win.undo_action.trigger()
        assert (root / "a.txt").exists()           # 撤销恢复
    finally:
        win.close()
