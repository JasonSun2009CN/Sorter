# =============================================================================
# app/gui/preview_view.py —— 变更预览视图（工作流步骤 ④，Phase 6）
#
# 作用：
#   把 Phase 6 生成的 PreviewReport 渲染成清晰的 old→new 清单，
#   并分开展示冲突与警告 —— 应用变更前的安全检查。本视图只读，不执行。
#
# 结构：
#   class PreviewView(QWidget)
#       load_preview(report, root=None)   # 渲染报告（公开 API，可离屏测试）
#       clear()                           # 回到空态
#       back 信号                          # 「← 返回规则」
# =============================================================================

"""变更预览视图：展示移动清单、冲突与警告（干跑）。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.preview import PreviewReport
from app.gui.theme import DANGER

_COLUMNS = ["文件名", "当前目录", "目标目录", "状态"]


class PreviewView(QWidget):
    """工作流第 ④ 步：预览变更。"""

    back = Signal()             # 「← 返回规则」
    apply_requested = Signal()  # 「应用变更」被点击

    def __init__(self) -> None:
        super().__init__()
        self._report: PreviewReport | None = None
        self._root: Path | None = None
        self._build_ui()
        self.clear()

    # ---- 界面 ----

    def _build_ui(self) -> None:
        header = QLabel("④ 变更预览")
        header.setStyleSheet("font-size:16px; font-weight:600;")

        self._summary = QLabel()
        self._summary.setWordWrap(True)

        self._table = self._make_table()

        # 冲突面板
        self._conflicts_title = QLabel("冲突（以下文件不会执行）")
        self._conflicts_title.setStyleSheet(f"color:{DANGER}; font-weight:600;")
        self._conflicts_list = QListWidget()
        self._conflicts_list.setSelectionMode(QListWidget.NoSelection)
        self._conflicts_panel = QWidget()
        panel = QVBoxLayout(self._conflicts_panel)
        panel.setContentsMargins(0, 8, 0, 0)
        panel.addWidget(self._conflicts_title)
        panel.addWidget(self._conflicts_list)

        # 警告面板
        self._warnings_title = QLabel("警告")
        self._warnings_title.setStyleSheet("font-weight:600;")
        self._warnings_list = QListWidget()
        self._warnings_list.setSelectionMode(QListWidget.NoSelection)
        self._warnings_panel = QWidget()
        panel = QVBoxLayout(self._warnings_panel)
        panel.setContentsMargins(0, 8, 0, 0)
        panel.addWidget(self._warnings_title)
        panel.addWidget(self._warnings_list)

        self._empty_hint = QLabel("规则未匹配任何文件，无需移动")
        self._empty_hint.setAlignment(Qt.AlignCenter)
        self._empty_hint.setStyleSheet("color:#64748B; font-size:15px;")

        self._back_btn = QPushButton("← 返回规则")
        self._back_btn.setObjectName("ghost")
        self._back_btn.clicked.connect(self.back.emit)

        self._apply_btn = QPushButton("应用变更")
        self._apply_btn.setObjectName("accent")
        self._apply_btn.setEnabled(False)
        self._apply_btn.setToolTip("执行移动（可撤销）")
        self._apply_btn.clicked.connect(self.apply_requested.emit)

        bottom = QHBoxLayout()
        bottom.addWidget(self._back_btn)
        bottom.addStretch(1)
        bottom.addWidget(self._apply_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(self._summary)
        layout.addWidget(self._table, 1)
        layout.addWidget(self._conflicts_panel)
        layout.addWidget(self._warnings_panel)
        layout.addWidget(self._empty_hint)
        layout.addLayout(bottom)

    @staticmethod
    def _make_table() -> QTableWidget:
        """预览专用表格：目录两列弹性伸缩，只读无选中。"""
        table = QTableWidget(0, len(_COLUMNS))
        table.setHorizontalHeaderLabels(_COLUMNS)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.NoSelection)  # 防 QSS 选中色覆盖冲突红字
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.setColumnWidth(0, 240)
        table.setColumnWidth(3, 90)
        return table

    # ---- 对外接口 ----

    def load_preview(self, report: PreviewReport, root: "str | Path | None" = None) -> None:
        """渲染一次干跑报告；moves 为空则显示空态。"""
        self._report = report
        self._root = Path(root).expanduser().resolve() if root else None
        summary = report.summary
        if summary["total"] == 0:
            self.clear()
            return

        self._apply_btn.setEnabled(bool(report.safe_moves))
        self._empty_hint.setVisible(False)
        self._table.setVisible(True)
        self._summary.setVisible(True)

        parts = [f"将移动 {summary['total']} 个文件"]
        if summary["blocked_count"]:
            parts.append(f"{summary['blocked_count']} 个冲突（不会执行）")
        if summary["warning_count"]:
            parts.append(f"{summary['warning_count']} 条警告")
        breakdown = " · ".join(f"{k} {v}" for k, v in summary["by_reason"].items())
        self._summary.setText(" · ".join(parts) + (f"\n{breakdown}" if breakdown else ""))

        blocked = report.blocked_sources
        self._table.setRowCount(0)
        for m in report.moves:
            conflicted = m.source in blocked
            cells = [
                m.source.name,
                self._rel(m.source.parent),
                m.reason or self._rel(m.target.parent),
                "⚠ 冲突" if conflicted else "✓ 将移动",
            ]
            row = self._table.rowCount()
            self._table.insertRow(row)
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if conflicted:
                    item.setForeground(QColor(DANGER))
                if col == 0:
                    item.setToolTip(str(m.source))
                elif col == 2:
                    item.setToolTip(str(m.target))
                self._table.setItem(row, col, item)

        self._conflicts_list.clear()
        for c in report.conflicts:
            self._conflicts_list.addItem(f"{c.message}（{len(c.moves)} 个文件）")
        self._conflicts_panel.setVisible(bool(report.conflicts))

        self._warnings_list.clear()
        for w in report.warnings:
            self._warnings_list.addItem(w)
        self._warnings_panel.setVisible(bool(report.warnings))

    def clear(self) -> None:
        """回到空态（无计划）。"""
        self._report = None
        self._apply_btn.setEnabled(False)
        self._summary.setVisible(False)
        self._table.setVisible(False)
        self._conflicts_panel.setVisible(False)
        self._warnings_panel.setVisible(False)
        self._empty_hint.setVisible(True)

    # ---- 辅助 ----

    def _rel(self, path: Path) -> str:
        """相对根目录显示路径；不在根下则回退绝对路径。"""
        if self._root is None:
            return str(path)
        try:
            return str(path.relative_to(self._root))
        except ValueError:
            return str(path)
