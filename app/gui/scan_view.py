# =============================================================================
# app/gui/scan_view.py —— 扫描视图（工作流步骤 ①）
#
# 作用：
#   让用户选择要整理的文件夹，发起递归扫描（后台线程），
#   展示进度与已索引文件列表，扫描完成后发出 files_scanned 信号。
#
# 结构：
#   class ScanView(QWidget)
#       _build_ui()               # 目录选择 + 开始扫描 + 进度条 + 文件表格
#       select_folder()           # 打开目录选择对话框
#       set_folder(path)          # 外部（菜单）指定目录
#       start_scan()              # 启动 ScanWorker 后台扫描
#       files_scanned 信号        # 交给 MainWindow 流转到标签审核
# =============================================================================

"""扫描视图：选择文件夹、递归扫描、展示文件列表。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.scanner import ScannedFile
from app.gui.formatting import format_mtime, format_size
from app.gui.widgets import make_file_table
from app.gui.workers import ScanWorker, start_worker, stop_thread


class ScanView(QWidget):
    """工作流第 ① 步：选择范围并扫描。"""

    files_scanned = Signal(list)  # list[ScannedFile]

    def __init__(self, db_path: "str | Path") -> None:
        super().__init__()
        self._db_path = str(db_path)
        self._thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        self._folder_edit = QLineEdit()
        self._folder_edit.setReadOnly(True)
        self._folder_edit.setPlaceholderText("选择要整理的文件夹…")

        self._select_btn = QPushButton("选择文件夹")
        self._select_btn.setObjectName("ghost")
        self._select_btn.clicked.connect(self.select_folder)

        self._scan_btn = QPushButton("开始扫描")
        self._scan_btn.setObjectName("accent")
        self._scan_btn.setEnabled(False)
        self._scan_btn.clicked.connect(self.start_scan)

        row = QHBoxLayout()
        row.addWidget(self._folder_edit, 1)
        row.addWidget(self._select_btn)
        row.addWidget(self._scan_btn)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setTextVisible(False)

        self._table = make_file_table()

        self._status = QLabel("尚未扫描")
        self._status.setObjectName("hint")

        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self._progress)
        layout.addWidget(self._table, 1)
        layout.addWidget(self._status)

    # ---- 公开操作 ----

    def select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "选择要整理的文件夹", str(Path.home())
        )
        if folder:
            self.set_folder(folder)

    def set_folder(self, folder: "str | Path") -> None:
        """由界面或菜单设置扫描目录，并允许开始扫描。"""
        self._folder_edit.setText(str(folder))
        self._scan_btn.setEnabled(True)
        self._status.setText("已选择目录，点击「开始扫描」")

    def folder(self) -> str:
        """返回当前选择的扫描目录（空串表示尚未选择）。"""
        return self._folder_edit.text()

    def start_scan(self) -> None:
        """启动后台扫描；正在扫描时忽略重复调用。"""
        folder = self._folder_edit.text()
        if not folder or self._thread is not None:
            return
        self._set_scanning(True)
        worker = ScanWorker(self._db_path, folder)
        worker.progress.connect(self._status.setText)
        worker.finished.connect(self._on_scan_done)
        worker.error.connect(self._on_scan_error)
        self._thread = start_worker(worker, self)

    def closeEvent(self, event) -> None:
        """关闭前等待扫描线程结束，避免 QThread 随窗口销毁导致崩溃。"""
        stop_thread(self._thread)
        super().closeEvent(event)

    # ---- 内部槽 ----

    def _set_scanning(self, scanning: bool) -> None:
        self._select_btn.setEnabled(not scanning)
        self._scan_btn.setEnabled(not scanning)
        self._scan_btn.setText("扫描中…" if scanning else "开始扫描")
        self._progress.setVisible(scanning)
        if scanning:
            self._progress.setRange(0, 0)  # 不确定进度
            self._status.setText("正在扫描目录…")

    def _on_scan_done(self, files: list[ScannedFile]) -> None:
        self._thread = None
        self._set_scanning(False)
        self._table.setRowCount(0)
        for f in files:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(f.name))
            self._table.setItem(row, 1, QTableWidgetItem(format_size(f.size)))
            self._table.setItem(row, 2, QTableWidgetItem(format_mtime(f.mtime)))
        self._status.setText(f"已扫描 {len(files)} 个文件")
        self.files_scanned.emit(files)

    def _on_scan_error(self, message: str) -> None:
        self._thread = None
        self._set_scanning(False)
        QMessageBox.critical(self, "扫描失败", message)
        self._status.setText("扫描失败")
