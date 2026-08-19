# =============================================================================
# app/gui/rules_view.py —— 组织规则视图（工作流步骤 ③，Phase 5）
#
# 作用：
#   让用户定义「具有这些属性的文件如何归档」—— 一条按顺序求值的目录层级
#   规则，并在右侧实时预览目标目录结构与文件分布。规则保存到 rules 表，
#   跨会话恢复。
#
# 公开 API（不经模态对话框，可离屏测试）：
#   load_files(files, root) / load_rule(name, rule) / load_last_rule()
#   current_rule() / rule_name() / add_level(level) / remove_level(i) / move_level(i, delta)
#   finished 信号              # 「完成 / 下一步」→ 预览占位页
#
# 结构：
#   class RulesView(QWidget)
#       _build_ui() / _render_levels() / _refresh_preview()
#       _add_tag_level()       # 对话框包装 add_level
#       _save_rule()           # 持久化
# =============================================================================

"""组织规则视图：构建目录层级规则并预览目标结构。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.core.organizer import (
    KIND_EXTENSION,
    KIND_TAG,
    KIND_TYPE,
    KIND_YEAR_CREATED,
    KIND_YEAR_MODIFIED,
    Rule,
    RuleLevel,
    build_plan,
    describe_level,
)
from app.core.scanner import ScannedFile
from app.database import Database
from app.database.queries import get_tags_by_path
from app.database.rules import get_last_rule, save_rule


class RulesView(QWidget):
    """工作流第 ③ 步：定义组织规则。"""

    finished = Signal()  # 「完成 / 下一步」被点击

    def __init__(self, db: Database) -> None:
        super().__init__()
        self._db = db
        self._files: list[ScannedFile] = []
        self._root: Path | None = None
        self._tags_by_path: dict[str, set[str]] = {}
        self._rule = Rule()
        self._build_ui()
        self.load_last_rule()  # 恢复上次保存的规则

    # ---- 界面 ----

    def _build_ui(self) -> None:
        header = QLabel("③ 定义组织规则")
        header.setStyleSheet("font-size:16px; font-weight:600;")

        # ---- 左栏：规则构建 ----
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("默认规则")

        self._levels_container = QWidget()
        self._levels_layout = QVBoxLayout(self._levels_container)
        self._levels_layout.setAlignment(Qt.AlignTop)
        self._levels_layout.setSpacing(6)

        levels_scroll = QScrollArea()
        levels_scroll.setWidgetResizable(True)
        levels_scroll.setWidget(self._levels_container)

        self._empty_hint = QLabel("规则为空，文件将不被移动")
        self._empty_hint.setStyleSheet("color:#64748B;")
        self._levels_layout.addWidget(self._empty_hint)

        add_row = QHBoxLayout()
        add_row.setSpacing(6)
        for label, handler in [
            ("＋ 按标签", self._add_tag_level),
            ("＋ 按类型", lambda: self.add_level(RuleLevel(KIND_TYPE))),
            ("＋ 按扩展名", lambda: self.add_level(RuleLevel(KIND_EXTENSION))),
            ("＋ 按创建年份", lambda: self.add_level(RuleLevel(KIND_YEAR_CREATED))),
            ("＋ 按修改年份", lambda: self.add_level(RuleLevel(KIND_YEAR_MODIFIED))),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("ghost")
            btn.clicked.connect(handler)
            add_row.addWidget(btn)
        add_row.addStretch(1)

        self._save_status = QLabel("")
        self._save_status.setStyleSheet("color:#0D9488;")

        self._save_btn = QPushButton("保存规则")
        self._save_btn.clicked.connect(self._save_rule)

        self._done_btn = QPushButton("完成 / 下一步")
        self._done_btn.setObjectName("accent")
        self._done_btn.clicked.connect(self.finished.emit)

        bottom = QHBoxLayout()
        bottom.addWidget(self._save_btn)
        bottom.addStretch(1)
        bottom.addWidget(self._done_btn)

        left = QVBoxLayout()
        left.addWidget(QLabel("规则名称"))
        left.addWidget(self._name_edit)
        left.addWidget(QLabel("目录层级（从上到下）"))
        left.addWidget(levels_scroll, 1)
        left.addLayout(add_row)
        left.addWidget(self._save_status)
        left.addLayout(bottom)

        # ---- 右栏：目标结构预览 ----
        self._preview_list = QListWidget()
        self._preview_list.setSelectionMode(QListWidget.NoSelection)
        right = QVBoxLayout()
        right.addWidget(QLabel("目标结构预览"))
        right.addWidget(self._preview_list)

        splitter = QSplitter(Qt.Horizontal)
        self._left_panel = QWidget()
        self._left_panel.setLayout(left)
        splitter.addWidget(self._left_panel)
        right_panel = QWidget()
        right_panel.setLayout(right)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([620, 480])

        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(splitter, 1)

    # ---- 对外接口 ----

    def load_files(self, files: list[ScannedFile], root: "str | Path | None") -> None:
        """载入当前扫描的文件与根目录，并刷新预览。"""
        self._files = list(files)
        self._root = Path(root).expanduser().resolve() if root else None
        self._tags_by_path = get_tags_by_path(self._db)
        self._refresh_preview()

    def load_rule(self, name: str, rule: Rule) -> None:
        """用给定规则填充构建器。"""
        self._name_edit.setText(name)
        self._rule = rule
        self._render_levels()
        self._refresh_preview()

    def load_last_rule(self) -> None:
        """恢复最近保存的规则（若有）。"""
        last = get_last_rule(self._db)
        if last is not None:
            self.load_rule(last[0], last[1])

    def current_rule(self) -> Rule:
        """返回当前构建中的规则。"""
        return self._rule

    def rule_name(self) -> str:
        """返回规则名（空则用默认名）。"""
        return self._name_edit.text().strip() or "默认规则"

    # ---- 规则编辑（不经对话框，可测试） ----

    def add_level(self, level: RuleLevel) -> None:
        self._rule.levels.append(level)
        self._render_levels()
        self._refresh_preview()

    def remove_level(self, index: int) -> None:
        if 0 <= index < len(self._rule.levels):
            del self._rule.levels[index]
            self._render_levels()
            self._refresh_preview()

    def move_level(self, index: int, delta: int) -> None:
        """把第 index 层上移(delta=-1)或下移(delta=1)；越界则忽略。"""
        j = index + delta
        if 0 <= index < len(self._rule.levels) and 0 <= j < len(self._rule.levels):
            self._rule.levels[index], self._rule.levels[j] = (
                self._rule.levels[j],
                self._rule.levels[index],
            )
            self._render_levels()
            self._refresh_preview()

    # ---- 内部 ----

    def _available_tags(self) -> list[str]:
        """可选作目录层级的标签：user / learned（Subject 类标签）。"""
        rows = self._db.query(
            "SELECT DISTINCT t.name AS name FROM tags t "
            "WHERE t.kind IN ('user', 'learned') ORDER BY t.name"
        )
        return [row["name"] for row in rows]

    def _add_tag_level(self) -> None:
        tags = self._available_tags()
        if not tags:
            self._save_status.setText("暂无 user/learned 标签可作目录（先在标签页添加）")
            self._save_status.setStyleSheet("color:#E11D48;")
            return
        tag, ok = QInputDialog.getItem(self, "按标签", "选择标签：", tags, 0, False)
        if ok and tag:
            self.add_level(RuleLevel(KIND_TAG, tag))

    def _save_rule(self) -> None:
        save_rule(self._db, self.rule_name(), self.current_rule())
        self._save_status.setText("已保存")
        self._save_status.setStyleSheet("color:#0D9488;")

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while (item := layout.takeAt(0)) is not None:
            if item.widget() is not None:
                item.widget().deleteLater()

    def _render_levels(self) -> None:
        self._clear_layout(self._levels_layout)
        levels = self._rule.levels
        for index, level in enumerate(levels):
            label = QLabel(describe_level(level))
            up = QPushButton("↑")
            down = QPushButton("↓")
            remove = QPushButton("删除")
            up.setObjectName("small")
            down.setObjectName("small")
            remove.setObjectName("danger")
            up.setEnabled(index > 0)
            down.setEnabled(index < len(levels) - 1)
            up.clicked.connect(lambda _=False, i=index: self.move_level(i, -1))
            down.clicked.connect(lambda _=False, i=index: self.move_level(i, 1))
            remove.clicked.connect(lambda _=False, i=index: self.remove_level(i))

            row = QHBoxLayout()
            row.addWidget(label)
            row.addStretch(1)
            row.addWidget(up)
            row.addWidget(down)
            row.addWidget(remove)
            self._levels_layout.addLayout(row)
        if not levels:
            hint = QLabel("规则为空，文件将不被移动")
            hint.setStyleSheet("color:#64748B;")
            self._levels_layout.addWidget(hint)
        self._levels_layout.addStretch(1)

    def _refresh_preview(self) -> None:
        self._preview_list.clear()
        if not self._rule.levels:
            self._preview_list.addItem("规则为空，文件将不被移动")
            return
        if self._root is None or not self._files:
            self._preview_list.addItem("尚未扫描文件")
            return
        plans = build_plan(
            [(f, self._tags_by_path.get(str(f.path), set())) for f in self._files],
            self._rule,
            self._root,
        )
        counts: dict[str, int] = {}
        for plan in plans:
            counts[plan.reason] = counts.get(plan.reason, 0) + 1
        for reason in sorted(counts):
            self._preview_list.addItem(f"{reason} — {counts[reason]} 个文件")
        unmatched = len(self._files) - len(plans)
        if unmatched:
            self._preview_list.addItem(f"未匹配（不移动）— {unmatched} 个文件")
