"""Sorter —— 本地优先的个人文件整理工具。入口脚本。

用法：python main.py
"""

from __future__ import annotations

import sys
from pathlib import Path


def _default_db_path() -> Path:
    """数据库默认位置：用户数据目录 ~/.sorter/sorter.db。"""
    return Path.home() / ".sorter" / "sorter.db"


def main() -> None:
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from app.database import Database
    from app.gui.main_window import MainWindow
    from app.gui.theme import apply_theme

    db_path = _default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.initialize()

    app = QApplication(sys.argv)
    app.setApplicationName("Sorter")
    app.setApplicationDisplayName("Sorter 文件整理")
    app.setOrganizationName("sorter")
    # 扁平主题 + Fusion 风格保证跨平台一致观感；中文字体兜底
    app.setStyle("Fusion")
    app.setFont(QFont("PingFang SC", 13))
    apply_theme(app)

    window = MainWindow(db)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
