# =============================================================================
# app/core/organizer.py —— 组织引擎（Phase 5：规则 → 目标路径）
#
# 作用：
#   根据用户规则为每个文件计算目标路径。本模块只“计划”不“执行”，
#   实际的移动发生在用户确认之后（Phase 7）。
#
# 规则模型（五类维度，两种语义）：
#   tag           过滤器 + 标签：文件必须拥有该标签规则才适用；
#                目录段 = 清洗后的标签名；缺标签 → 规则不适用，文件不动。
#   type/extension/year_created/year_modified   分组维度：由文件自身属性
#                计算目录段，永不失败（有兜底值）。
#   规则整体 all-or-nothing：任一 tag 层缺失 → 该文件不移动。
#
# 结构：
#   @dataclass RuleLevel / Rule / MovePlan
#   apply_level(file, tags, level) -> str | None     # 单层目录段
#   compute_target(file, tags, rule) -> Path | None  # 相对目标目录
#   build_plan(files_with_tags, rule, root) -> list[MovePlan]
#   _sanitize_segment(raw) / _same_location(a, b)
#   rule_to_dict(rule) / rule_from_dict(d)
#   describe_level(level)                            # UI 展示用
# =============================================================================

"""组织引擎：规则模型与目标路径计算（纯逻辑，可单测）。"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.core import metadata
from app.core.scanner import ScannedFile

# 规则维度种类
KIND_TAG = "tag"
KIND_TYPE = "type"
KIND_EXTENSION = "extension"
KIND_YEAR_CREATED = "year_created"
KIND_YEAR_MODIFIED = "year_modified"
RULE_KINDS = frozenset({KIND_TAG, KIND_TYPE, KIND_EXTENSION, KIND_YEAR_CREATED, KIND_YEAR_MODIFIED})

# 兜底目录段
FALLBACK_OTHER = "其他"
FALLBACK_UNKNOWN = "未知"

# 控制字符（0x00-0x1f, 0x7f）
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


@dataclass
class RuleLevel:
    """规则的一层：一个目录维度。

    ``kind`` 见 RULE_KINDS；``value`` 仅在 kind='tag' 时有意义（标签名）。
    """

    kind: str
    value: str = ""


@dataclass
class Rule:
    """一条组织规则 = 按顺序求值的目录层级列表。"""

    levels: list[RuleLevel] = field(default_factory=list)


@dataclass
class MovePlan:
    """为单个文件计算出的移动计划（不触碰文件）。"""

    source: Path
    target: Path
    reason: str  # 相对目录，如 "School/PDF"，供预览聚合


# ---- 单层求值 ----

def _year(timestamp: float) -> str:
    """时间戳 → 年份字符串；非法时间戳（<=0）返回「未知」。"""
    if timestamp <= 0:
        return FALLBACK_UNKNOWN
    return str(datetime.fromtimestamp(timestamp).year)


def apply_level(file: ScannedFile, tags: set[str], level: RuleLevel) -> str | None:
    """计算一层目录段。

    返回 None 表示该层不适用（仅 tag 层可能不适用）→ 规则整体不适用。
    """
    if level.kind == KIND_TAG:
        if level.value not in tags:
            return None
        return _sanitize_segment(level.value)
    if level.kind == KIND_TYPE:
        type_tag = metadata.infer_type(file.extension)
        if type_tag == "other":
            ext = file.extension.upper().lstrip(".")
            return ext or FALLBACK_OTHER
        return type_tag.upper()
    if level.kind == KIND_EXTENSION:
        ext = file.extension.upper().lstrip(".")
        return ext or FALLBACK_OTHER
    if level.kind == KIND_YEAR_CREATED:
        return _year(file.ctime)
    if level.kind == KIND_YEAR_MODIFIED:
        return _year(file.mtime)
    return None  # 未知 kind，视为不适用


def compute_target(file: ScannedFile, tags: set[str], rule: Rule) -> Path | None:
    """按规则计算相对目标目录（如 ``School/PDF``）；任一 tag 层缺失返回 None。"""
    segments: list[str] = []
    for level in rule.levels:
        segment = apply_level(file, tags, level)
        if segment is None:
            return None
        segments.append(segment)
    if not segments:
        return None
    return Path(*segments)


# ---- 路径安全 ----

def _sanitize_segment(raw: str) -> str:
    """把一个自由文本（标签名）清洗成安全的单一目录段。

    绝不返回路径分隔符或 ``..``：分隔符 / 控制字符替换为 ``_``，
    ``..`` 中和为 ``_``（因分隔符已被替换，无法绕过），前导点替换为 ``_``，
    去除尾部点 / 空格。非 ASCII（如中文）原样保留。
    """
    s = raw.strip()
    if not s:
        return FALLBACK_OTHER
    s = _CONTROL_RE.sub("_", s)
    s = s.replace("/", "_").replace("\\", "_").replace(":", "_")
    if s == "..":
        s = "_"
    if s.startswith("."):
        s = "_" + s.lstrip(".")
    s = s.rstrip(". ")
    return s or FALLBACK_OTHER


def _same_location(a: Path, b: Path) -> bool:
    """判断两个路径是否指向同一位置（macOS/Windows 大小写不敏感）。"""
    ra = str(a.expanduser().resolve())
    rb = str(b.expanduser().resolve())
    if sys.platform == "win32":
        return ra.lower() == rb.lower()
    if sys.platform == "darwin":
        return ra.casefold() == rb.casefold()
    return ra == rb


# ---- 计划 ----

def build_plan(
    files_with_tags: Iterable[tuple[ScannedFile, set[str]]],
    rule: Rule,
    root: "str | Path",
) -> list[MovePlan]:
    """为给定文件按规则计算移动计划（只计划不执行）。

    - 规则不适用（tag 缺失）或空规则 → 不产生 MovePlan（文件不动）；
    - 目标路径与当前相同（已就位）→ 跳过，保证幂等；
    - 返回按 source 排序的 MovePlan 列表。
    """
    if not rule.levels:
        return []
    root = Path(root).expanduser().resolve()
    plans: list[MovePlan] = []
    for file, tags in files_with_tags:
        relative = compute_target(file, tags, rule)
        if relative is None:
            continue
        target = root / relative / file.name
        if _same_location(file.path, target):
            continue
        plans.append(MovePlan(source=file.path, target=target, reason=str(relative)))
    plans.sort(key=lambda p: str(p.source))
    return plans


# ---- 序列化 ----

def rule_to_dict(rule: Rule) -> dict:
    """把规则转成可 JSON 序列化的字典。"""
    return {"levels": [{"kind": level.kind, "value": level.value} for level in rule.levels]}


def rule_from_dict(data: dict) -> Rule:
    """从字典还原规则；未知 kind 的层级被忽略。"""
    rule = Rule()
    for item in data.get("levels", []):
        kind = item.get("kind", "")
        if kind in RULE_KINDS:
            rule.levels.append(RuleLevel(kind=kind, value=str(item.get("value", ""))))
    return rule


# ---- UI 展示 ----

def describe_level(level: RuleLevel) -> str:
    """规则层级的可读描述，供规则构建界面展示。"""
    if level.kind == KIND_TAG:
        return f"按标签：{level.value or '（未指定）'}"
    labels = {
        KIND_TYPE: "按文件类型",
        KIND_EXTENSION: "按扩展名",
        KIND_YEAR_CREATED: "按创建年份",
        KIND_YEAR_MODIFIED: "按修改年份",
    }
    return labels.get(level.kind, f"未知维度：{level.kind}")


# ---- Phase 7 预留 ----

def apply_plan(plans: list[MovePlan]) -> object:
    """实际移动文件并生成操作记录（Phase 7 实现）。"""
    raise NotImplementedError("apply_plan 在 Phase 7 实现")


def _resolve_conflicts(plans: list[MovePlan]) -> list[MovePlan]:
    """重名 / 目标冲突处理（Phase 7 实现）。"""
    raise NotImplementedError("_resolve_conflicts 在 Phase 7 实现")
