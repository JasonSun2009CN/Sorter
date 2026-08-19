# =============================================================================
# app/gui/tag_view.py —— 标签审核视图（工作流步骤 ②，Phase 4 核心）
#
# 作用：
#   展示每个文件的标签与置信度，允许用户接受 / 拒绝 / 增删标签。
#   所有修改直接写入数据库（数据库是唯一事实来源），每次选中 / 操作后
#   从数据库重渲染，界面状态不会漂移。用户修正存入 training_feedback，
#   供后续个性化重训练使用。
#
# 交互语义：
#   系统标签   只读 chip，展示确定性结果
#   学习标签   chip 带置信度；✓ 接受（写入 accepted=1 反馈）、✗ 拒绝
#             （写入 accepted=0 反馈并移除该 file_tags 行）
#   用户标签   可添加 / 移除（source='user'）
#
# 结构：
#   class TagView(QWidget)
#       load_files(files)           # 从扫描结果加载文件列表
#       _render_tags(file_id)       # 从 DB 重建标签 chips
#       _accept / _reject / _add_user_tag / _remove_user_tag
#       finished 信号               # 「完成 / 下一步」→ 规则占位页
# =============================================================================

"""标签审核视图：展示标签与置信度，接受 / 拒绝 / 增删。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.scanner import ScannedFile
from app.database import Database
from app.database.queries import (
    add_user_tag,
    get_file_tags,
    remove_user_tag,
    set_tag_accepted,
)
from app.gui.formatting import format_mtime, format_size
from app.gui.widgets import make_file_table

# chip 内联样式
_STYLE_SYSTEM = "background:#CCFBF1; color:#134E4A; border-radius:6px; padding:4px 10px;"
_STYLE_LEARNED = (
    "background:#FFFFFF; color:#134E4A; border:1px solid #99F6E4;"
    "border-radius:6px; padding:4px 10px;"
)
_STYLE_ACCEPTED = "background:#0D9488; color:#FFFFFF; border-radius:6px; padding:4px 10px;"
_STYLE_USER = (
    "background:#FFF7ED; color:#9A3412; border:1px solid #FDBA74;"
    "border-radius:6px; padding:4px 10px;"
)
_STYLE_HINT = "color:#64748B; font-size:12px;"


class TagView(QWidget):
    """工作流第 ② 步：审核标签。"""

    finished = Signal()  # 「完成 / 下一步」被点击

    def __init__(self, db: Database) -> None:
        super().__init__()
        self._db = db
        self._build_ui()

    def _build_ui(self) -> None:
        # ---- 左侧：文件列表 ----
        self._table = make_file_table(on_select=self._on_file_selected)

        # ---- 右侧：标签详情 ----
        self._header = QLabel("选择左侧文件以查看标签")
        self._header.setWordWrap(True)

        self._tags_container = QWidget()
        self._tags_layout = QVBoxLayout(self._tags_container)
        self._tags_layout.setAlignment(Qt.AlignTop)
        self._tags_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._tags_container)

        self._add_btn = QPushButton("＋ 添加标签")
        self._add_btn.setObjectName("ghost")
        self._add_btn.clicked.connect(self._add_user_tag)

        self._done_btn = QPushButton("完成 / 下一步")
        self._done_btn.setObjectName("accent")
        self._done_btn.clicked.connect(self.finished.emit)

        bottom = QHBoxLayout()
        bottom.addWidget(self._add_btn)
        bottom.addStretch(1)
        bottom.addWidget(self._done_btn)

        right = QVBoxLayout()
        right.addWidget(self._header)
        right.addWidget(scroll, 1)
        right.addLayout(bottom)

        self._panel = QWidget()
        self._panel.setLayout(right)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._table)
        splitter.addWidget(self._panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([640, 460])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    # ---- 对外接口 ----

    def load_files(self, files: list[ScannedFile]) -> None:
        """加载扫描结果；逐个文件取 file_id 并填入表格。"""
        self._table.setRowCount(0)
        for f in files:
            row = self._db.get_file_by_path(str(f.path))
            if row is None:
                continue  # 未索引，跳过
            r = self._table.rowCount()
            self._table.insertRow(r)
            name_item = QTableWidgetItem(f.name)
            name_item.setData(Qt.UserRole, row["id"])  # file_id 挂在第 0 列
            self._table.setItem(r, 0, name_item)
            self._table.setItem(r, 1, QTableWidgetItem(format_size(f.size)))
            self._table.setItem(r, 2, QTableWidgetItem(format_mtime(f.mtime)))
        self._header.setText("选择左侧文件以查看标签")
        self._clear_tags()
        if self._table.rowCount() > 0:
            self._table.setCurrentCell(0, 0)

    # ---- 选中 / 渲染 ----

    def _on_file_selected(self, _current: QTableWidgetItem | None, _previous: QTableWidgetItem | None) -> None:
        file_id = self._current_file_id()
        if file_id is None:
            self._header.setText("选择左侧文件以查看标签")
            self._clear_tags()
            return
        rows = self._db.query(
            "SELECT path, size, mtime FROM files WHERE id = ?", (file_id,)
        )
        if rows:
            info = rows[0]
            self._header.setText(
                f"{info['path']}\n{format_size(info['size'])} · {format_mtime(info['mtime'])}"
            )
        self._render_tags(file_id)

    def _current_file_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _clear_tags(self) -> None:
        while (item := self._tags_layout.takeAt(0)) is not None:
            if item.widget() is not None:
                item.widget().deleteLater()

    def _render_tags(self, file_id: int) -> None:
        """从数据库读取该文件标签并重建 chips。"""
        self._clear_tags()
        tag_rows = get_file_tags(self._db, file_id)
        has_learned = False
        for r in tag_rows:
            kind = r["kind"]
            if kind == "system":
                row = self._chip_row(r["tag"], _STYLE_SYSTEM, [], file_id, r)
            elif kind == "learned":
                has_learned = True
                accepted = r["feedback"] == 1
                chip = r["tag"] + (f"  {int(r['confidence'] * 100)}%" if not accepted else "  ✓ 已接受")
                buttons = []
                if accepted:
                    buttons.append(("✗ 拒绝", "danger", self._reject))
                else:
                    buttons.append(("✓ 接受", "", self._accept))
                    buttons.append(("✗ 拒绝", "danger", self._reject))
                row = self._chip_row(chip, _STYLE_ACCEPTED if accepted else _STYLE_LEARNED, buttons, file_id, r)
            else:  # user
                row = self._chip_row(
                    r["tag"], _STYLE_USER, [("✗ 移除", "danger", self._remove_user_tag)], file_id, r
                )
            self._tags_layout.addLayout(row)
        if not has_learned:
            hint = QLabel("暂无学习标签 — 添加用户标签后重新扫描，将产生个性化预测")
            hint.setStyleSheet(_STYLE_HINT)
            hint.setWordWrap(True)
            self._tags_layout.addWidget(hint)
        self._tags_layout.addStretch(1)

    @staticmethod
    def _chip_row(label_text, style, buttons, file_id, row) -> QHBoxLayout:
        """构造一行 chip：标签 + 若干操作按钮。"""
        chip = QLabel(label_text)
        chip.setStyleSheet(style)
        line = QHBoxLayout()
        line.addWidget(chip)
        line.addStretch(1)
        for text, variant, handler in buttons:
            btn = QPushButton(text)
            btn.setObjectName("danger" if variant == "danger" else "small")
            btn.clicked.connect(
                lambda _=False, h=handler, fid=file_id, tag=row["tag"], src=row["source"]: h(fid, tag, src)
            )
            line.addWidget(btn)
        return line

    # ---- 操作槽 ----

    def _accept(self, file_id: int, tag: str, source: str) -> None:
        set_tag_accepted(self._db, file_id, tag, source=source, accepted=True)
        self._render_tags(file_id)

    def _reject(self, file_id: int, tag: str, source: str) -> None:
        set_tag_accepted(self._db, file_id, tag, source=source, accepted=False)
        self._render_tags(file_id)

    def _remove_user_tag(self, file_id: int, tag: str, _source: str) -> None:
        remove_user_tag(self._db, file_id, tag)
        self._render_tags(file_id)

    def _add_user_tag(self) -> None:
        file_id = self._current_file_id()
        if file_id is None:
            return
        text, ok = QInputDialog.getText(self, "添加标签", "输入新标签名称：")
        if ok and text.strip():
            add_user_tag(self._db, file_id, text.strip())
            self._render_tags(file_id)
