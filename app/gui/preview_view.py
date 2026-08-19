# =============================================================================
# app/gui/preview_view.py —— 变更预览视图（工作流步骤 ④，占位）
#
# 作用：
#   Phase 6 实现：展示 old→new 路径、冲突与警告，作为应用变更前的
#   安全检查。本阶段仅提供占位页，保持类名与 _build_ui 结构。
# =============================================================================

"""变更预览视图（Phase 6 占位页）。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PreviewView(QWidget):
    """工作流第 ④ 步：预览变更（待 Phase 6 实现）。"""

    def __init__(self) -> None:
        super().__init__()
        self._build_ui()

    def _build_ui(self) -> None:
        label = QLabel("变更预览（Phase 6）\n\n将在这里展示每个文件 old → new 路径、冲突与警告。敬请期待。")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color:#64748B; font-size:15px;")
        layout = QVBoxLayout(self)
        layout.addWidget(label)
