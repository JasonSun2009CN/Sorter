# =============================================================================
# app/gui/widgets.py —— 通用小部件工厂
#
# 作用：
#   抽取多个视图共用的小部件装配逻辑，避免重复代码。
#
# 结构：
#   make_file_table(on_select=None) -> QTableWidget
# =============================================================================

"""共享小部件：文件列表表格等。"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

_COLUMNS = ["文件名", "大小", "修改时间"]


def make_file_table(
    on_select: Callable[[QTableWidgetItem | None, QTableWidgetItem | None], object] | None = None,
) -> QTableWidget:
    """构造一个只读文件列表表格（三列：文件名 / 大小 / 修改时间）。

    传入 ``on_select`` 时用 currentItemChanged 连接选择回调（键盘导航也能触发）。
    """
    table = QTableWidget(0, len(_COLUMNS))
    table.setHorizontalHeaderLabels(_COLUMNS)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setSelectionMode(QTableWidget.SingleSelection)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.setColumnWidth(0, 320)
    table.setColumnWidth(1, 90)
    table.setColumnWidth(2, 130)
    if on_select is not None:
        table.currentItemChanged.connect(on_select)
    return table
