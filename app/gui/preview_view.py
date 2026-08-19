# =============================================================================
# app/gui/preview_view.py —— 变更预览视图（工作流步骤 ④）
#
# 作用：
#   把 PreviewReport 渲染成**文件树**（目录结构 → 文件）供用户确认，
#   并分开展示冲突与警告。自动整理模式下顶部提供「分类方式」选择
#   （标签 / 类型 / 年份 / 扩展名），变化时发出 dimensions_changed 重新生成。
#   本视图只读，不执行。
#
# 结构：
#   class PreviewView(QWidget)
#       load_preview(report, root=None, dimensions=None)
#       show_dimensions(visible)          # 自动模式显示分类方式选择行
#       clear()
#       back / apply_requested / dimensions_changed 信号
# =============================================================================

"""变更预览视图：文件树 + 分类方式选择 + 冲突 / 警告。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.autoplan import DIM_EXTENSION, DIM_TAG, DIM_TYPE, DIM_YEAR
from app.core.preview import PreviewReport
from app.gui.theme import DANGER

# 分类方式：固定顺序，勾选即作为目录层级
_DIMENSIONS_ORDER = (DIM_TAG, DIM_TYPE, DIM_YEAR, DIM_EXTENSION)
_DIMENSION_LABELS = {
    DIM_TAG: "按标签",
    DIM_TYPE: "按类型",
    DIM_YEAR: "按年份",
    DIM_EXTENSION: "按扩展名",
}


class PreviewView(QWidget):
    """工作流第 ④ 步：预览变更（文件树确认）。"""

    back = Signal()             # 「← 返回」
    apply_requested = Signal()  # 「应用变更」
    dimensions_changed = Signal(list)  # 分类方式变化 → [tag, type, ...]

    def __init__(self) -> None:
        super().__init__()
        self._report: PreviewReport | None = None
        self._root: Path | None = None
        self._updating = False
        self._dimensions: list[str] = [DIM_TAG, DIM_TYPE]
        self._build_ui()
        self._set_dimensions(self._dimensions)  # 同步默认勾选
        self.clear()

    # ---- 界面 ----

    def _build_ui(self) -> None:
        header = QLabel("④ 变更预览")
        header.setStyleSheet("font-size:16px; font-weight:600;")

        # 分类方式行（自动整理模式显示）
        self._dim_row = QWidget()
        dim_row = QHBoxLayout(self._dim_row)
        dim_row.setContentsMargins(0, 0, 0, 0)
        dim_row.addWidget(QLabel("分类方式："))
        self._dim_checkboxes: dict[str, QCheckBox] = {}
        for dim in _DIMENSIONS_ORDER:
            cb = QCheckBox(_DIMENSION_LABELS[dim])
            cb.stateChanged.connect(self._on_dim_toggled)
            self._dim_checkboxes[dim] = cb
            dim_row.addWidget(cb)
        dim_row.addStretch(1)

        self._summary = QLabel()
        self._summary.setWordWrap(True)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setSelectionMode(QTreeWidget.NoSelection)
        self._tree.setFocusPolicy(Qt.NoFocus)

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

        self._back_btn = QPushButton("← 返回")
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
        layout.addWidget(self._dim_row)
        layout.addWidget(self._summary)
        layout.addWidget(self._tree, 1)
        layout.addWidget(self._conflicts_panel)
        layout.addWidget(self._warnings_panel)
        layout.addWidget(self._empty_hint)
        layout.addLayout(bottom)

    # ---- 对外接口 ----

    def load_preview(
        self,
        report: PreviewReport,
        root: "str | Path | None" = None,
        dimensions: list[str] | None = None,
    ) -> None:
        """渲染一次干跑报告为文件树；moves 为空则显示空态。

        ``dimensions`` 非空时同步勾选状态（不触发重新生成）。
        """
        self._report = report
        self._root = Path(root).expanduser().resolve() if root else None
        if dimensions is not None:
            self._set_dimensions(dimensions)
        summary = report.summary
        if summary["total"] == 0:
            self.clear()
            return

        self._empty_hint.setVisible(False)
        self._tree.setVisible(True)
        self._summary.setVisible(True)

        parts = [f"将移动 {summary['total']} 个文件"]
        if summary["blocked_count"]:
            parts.append(f"{summary['blocked_count']} 个冲突（不会执行）")
        if summary["warning_count"]:
            parts.append(f"{summary['warning_count']} 条警告")
        breakdown = " · ".join(f"{k} {v}" for k, v in summary["by_reason"].items())
        self._summary.setText(" · ".join(parts) + (f"\n{breakdown}" if breakdown else ""))

        self._build_tree(report.moves, report.blocked_sources)
        self._apply_btn.setEnabled(bool(report.safe_moves))

        self._conflicts_list.clear()
        for c in report.conflicts:
            self._conflicts_list.addItem(f"{c.message}（{len(c.moves)} 个文件）")
        self._conflicts_panel.setVisible(bool(report.conflicts))

        self._warnings_list.clear()
        for w in report.warnings:
            self._warnings_list.addItem(w)
        self._warnings_panel.setVisible(bool(report.warnings))

    def show_dimensions(self, visible: bool) -> None:
        """自动整理模式显示分类方式选择行；手动模式隐藏。"""
        self._dim_row.setVisible(visible)

    def dimensions(self) -> list[str]:
        """当前勾选的分类方式。"""
        return list(self._dimensions)

    def clear(self) -> None:
        """回到空态（无计划）。"""
        self._report = None
        self._tree.clear()
        self._apply_btn.setEnabled(False)
        self._summary.setVisible(False)
        self._tree.setVisible(False)
        self._conflicts_panel.setVisible(False)
        self._warnings_panel.setVisible(False)
        self._empty_hint.setVisible(True)

    # ---- 分类方式 ----

    def _set_dimensions(self, dimensions: list[str]) -> None:
        """按给定维度同步勾选（guard 防止触发 dimensions_changed）。"""
        self._updating = True
        try:
            self._dimensions = [d for d in _DIMENSIONS_ORDER if d in dimensions]
            for dim, cb in self._dim_checkboxes.items():
                cb.setChecked(dim in self._dimensions)
        finally:
            self._updating = False

    def _on_dim_toggled(self) -> None:
        if self._updating:
            return
        self._dimensions = [d for d in _DIMENSIONS_ORDER if self._dim_checkboxes[d].isChecked()]
        self.dimensions_changed.emit(list(self._dimensions))

    # ---- 文件树 ----

    def _build_tree(self, moves: list, blocked: set) -> None:
        self._tree.clear()
        root_item = self._tree.invisibleRootItem()
        for m in sorted(moves, key=lambda p: (p.reason, str(p.source))):
            parent = root_item
            for part in m.reason.split("/"):
                child = self._find_child(parent, part)
                if child is None:
                    child = QTreeWidgetItem([part])
                    parent.addChild(child)
                parent = child
            leaf = QTreeWidgetItem([m.source.name])
            if m.source in blocked:
                leaf.setForeground(0, QColor(DANGER))
            parent.addChild(leaf)
        self._tree.expandAll()

    @staticmethod
    def _find_child(parent: QTreeWidgetItem, text: str) -> QTreeWidgetItem | None:
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.text(0) == text:
                return child
        return None
