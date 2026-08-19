# =============================================================================
# app/gui/main_window.py —— 主窗口（工作流中枢）
#
# 作用：
#   装配四个视图（扫描 → 标签审核 → 规则占位 → 预览占位）并通过
#   QStackedWidget 切换。扫描完成后在后台线程生成系统/学习标签，
#   再把结果交给标签审核视图。
#
# 结构：
#   class MainWindow(QMainWindow)
#       _setup_menu()             # 文件 / 编辑 / 帮助
#       _setup_stacked_widget()   # 视图容器
#       _run_worker(worker)       # 后台线程脚手架
#       _on_scan_finished / _on_tagging_finished / _on_tag_review_finished
#       switch_view(index)
# =============================================================================

"""主窗口：装配视图并驱动扫描 → 标签 → 规则 → 预览工作流。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
)

from app.database import Database
from app.gui.preview_view import PreviewView
from app.gui.rules_view import RulesView
from app.gui.scan_view import ScanView
from app.gui.tag_view import TagView
from app.gui.workers import TagWorker, start_worker, stop_thread


class MainWindow(QMainWindow):
    """应用主窗口。"""

    def __init__(self, db: Database) -> None:
        super().__init__()
        self._db = db
        self._thread = None
        self._setup_menu()
        self._setup_stacked_widget()
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)
        self.setWindowTitle("Sorter — 文件整理")

    # ---- 界面装配 ----

    def _setup_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        open_action = QAction("打开目录…", self)
        open_action.triggered.connect(self._open_folder)
        file_menu.addAction(open_action)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = self.menuBar().addMenu("编辑")
        undo_action = QAction("撤销", self)
        undo_action.setEnabled(False)
        undo_action.setStatusTip("撤销（Phase 7 实现）")
        edit_menu.addAction(undo_action)

        help_menu = self.menuBar().addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_stacked_widget(self) -> None:
        self.scan_view = ScanView(self._db.path)
        self.tag_view = TagView(self._db)
        self.rules_view = RulesView()
        self.preview_view = PreviewView()

        self.stack = QStackedWidget()
        self.stack.addWidget(self.scan_view)
        self.stack.addWidget(self.tag_view)
        self.stack.addWidget(self.rules_view)
        self.stack.addWidget(self.preview_view)
        self.setCentralWidget(self.stack)

        self.scan_view.files_scanned.connect(self._on_scan_finished)
        self.tag_view.finished.connect(self._on_tag_review_finished)
        self.switch_view(0)

    # ---- 工作流接线 ----

    def _open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "打开要整理的文件夹", str(Path.home()))
        if folder:
            self.scan_view.set_folder(folder)
            self.switch_view(0)
            self.scan_view.start_scan()

    def _on_scan_finished(self, files: list) -> None:
        if not files:
            self.statusBar().showMessage("扫描完成：未发现文件")
            return
        worker = TagWorker(self._db.path, files)
        worker.progress.connect(self.statusBar().showMessage)
        worker.finished.connect(self._on_tagging_finished)
        worker.error.connect(self._on_worker_error)
        self._thread = start_worker(worker, self)

    def _on_tagging_finished(self, files: list, n_system: int, n_learned: int) -> None:
        self._thread = None
        self.tag_view.load_files(files)
        self.switch_view(1)
        self.statusBar().showMessage(
            f"标签生成完成：系统 {n_system} 条，学习 {n_learned} 条"
        )

    def _on_tag_review_finished(self) -> None:
        self.switch_view(2)  # 规则占位页（Phase 5）

    def _on_worker_error(self, message: str) -> None:
        self._thread = None
        QMessageBox.critical(self, "处理失败", message)
        self.statusBar().showMessage("处理失败")

    # ---- 辅助 ----

    def switch_view(self, index: int) -> None:
        """切换到指定视图并给出状态栏提示。"""
        self.stack.setCurrentIndex(index)
        hints = {0: "① 选择文件夹并扫描", 1: "② 审核标签", 2: "③ 组织规则（下一阶段）", 3: "④ 预览（下一阶段）"}
        self.statusBar().showMessage(hints.get(index, ""))

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于 Sorter",
            "Sorter — 本地优先的个人文件整理工具。\n\n"
            "扫描文件夹 → 自动标签 → 审核修正 → 组织规则 → 安全应用。\n"
            "所有处理都在本机完成，不联网。",
        )

    def closeEvent(self, event) -> None:
        """关闭前等待后台标签线程结束，避免 QThread 随窗口销毁导致崩溃。"""
        stop_thread(self._thread)
        super().closeEvent(event)
