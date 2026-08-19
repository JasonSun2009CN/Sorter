# =============================================================================
# app/gui/rules_view.py —— 组织规则视图（工作流步骤 ③，占位）
#
# 作用：
#   Phase 5 实现：用户定义"标签 / 属性 → 目录结构"的组织规则。
#   本阶段仅提供占位页，保持类名与 _build_ui 结构，后续直接填充。
# =============================================================================

"""组织规则视图（Phase 5 占位页）。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class RulesView(QWidget):
    """工作流第 ③ 步：定义组织规则（待 Phase 5 实现）。"""

    def __init__(self) -> None:
        super().__init__()
        self._build_ui()

    def _build_ui(self) -> None:
        label = QLabel("组织规则（Phase 5）\n\n选择标签，定义文件如何归档到目录结构。敬请期待。")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color:#64748B; font-size:15px;")
        layout = QVBoxLayout(self)
        layout.addWidget(label)
