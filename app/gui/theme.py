# =============================================================================
# app/gui/theme.py —— 全局主题（扁平风）
#
# 作用：
#   集中定义颜色常量与全局 QSS，应用扁平设计（无渐变 / 无重阴影），
#   并提供 apply_theme(app) 一次性注入。
#
# 调色板（flat design）：
#   PRIMARY   teal      #0D9488
#   SECONDARY teal      #14B8A6
#   ACCENT    橙色       #F97316（主要动作按钮）
#   BG        浅青底     #F0FDFA
#   TEXT      深青字     #134E4A
# =============================================================================

"""扁平主题：颜色常量 + 全局 QSS + apply_theme。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

# ---- 调色板 ----
PRIMARY = "#0D9488"
SECONDARY = "#14B8A6"
ACCENT = "#F97316"
ACCENT_HOVER = "#EA580C"
BG = "#F0FDFA"
TEXT = "#134E4A"
MUTED = "#475569"
BORDER = "#99F6E4"
CHIP_BG = "#CCFBF1"
WHITE = "#FFFFFF"
DANGER = "#E11D48"

_QSS = f"""
QMainWindow, QWidget {{
    background: {BG};
    color: {TEXT};
    font-size: 13px;
}}
QLabel {{
    background: transparent;
}}
QPushButton {{
    background: {SECONDARY};
    color: {WHITE};
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
}}
QPushButton:hover {{ background: {PRIMARY}; }}
QPushButton:pressed {{ background: {PRIMARY}; }}
QPushButton:disabled {{ background: #CCFBF1; color: #99F6E4; }}
QPushButton:focus {{ border: 2px solid {ACCENT}; }}
QPushButton#accent {{ background: {ACCENT}; }}
QPushButton#accent:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#ghost {{
    background: transparent;
    color: {PRIMARY};
    border: 1px solid {BORDER};
}}
QPushButton#ghost:hover {{ background: {CHIP_BG}; }}
QPushButton#danger {{ background: transparent; color: {DANGER}; border: 1px solid #FDA4AF; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
QPushButton#danger:hover {{ background: #FFF1F2; }}
QPushButton#small {{ padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
QLineEdit, QTableWidget, QComboBox, QListWidget {{
    background: {WHITE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 6px;
    selection-background-color: {PRIMARY};
    selection-color: {WHITE};
}}
QLineEdit:focus {{ border-color: {PRIMARY}; }}
QTableWidget {{
    border: 1px solid {BORDER};
    gridline-color: #CCFBF1;
}}
QHeaderView::section {{
    background: {CHIP_BG};
    color: {TEXT};
    border: none;
    padding: 6px;
    font-weight: 600;
}}
QTableWidget::item:selected {{ background: {CHIP_BG}; color: #0F766E; }}
QProgressBar {{
    border: none;
    border-radius: 4px;
    background: {CHIP_BG};
    height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 4px; }}
QMenuBar {{ background: {CHIP_BG}; color: {TEXT}; }}
QMenuBar::item:selected {{ background: {PRIMARY}; color: {WHITE}; }}
QMenu {{ background: {WHITE}; border: 1px solid {BORDER}; }}
QMenu::item:selected {{ background: {CHIP_BG}; color: #0F766E; }}
QStatusBar {{ background: {CHIP_BG}; color: {TEXT}; }}
QScrollArea {{ border: none; background: transparent; }}
QToolTip {{ background: {TEXT}; color: {WHITE}; border: none; }}
"""


def apply_theme(app: "QApplication") -> None:
    """把全局 QSS 应用到 QApplication。"""
    app.setStyleSheet(_QSS)
