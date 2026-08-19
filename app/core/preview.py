# =============================================================================
# app/core/preview.py —— 变更预览 / 干跑（Phase 6）
#
# 作用：
#   安全机制的落地实现。把 Phase 5 的 MovePlan 渲染成可展示的预览报告：
#   old→new 清单 + 冲突 + 警告 + 摘要。绝不触碰文件（只读检查 + 内容哈希
#   用于重复检测）。
#
# 冲突语义（三种）：
#   collision  同名目标冲突：多个移动计划撞到同一目标路径
#   occupied   目标被占用：目标已存在（含悬空符号链接）且不是待移动文件
#   mutual     互换 / 成环：目标落在另一个待移动文件的源位置（A→B 且 B→A）
#
# 结构：
#   @dataclass PreviewConflict / PreviewReport
#   generate_preview(moves, *, extra_warnings=()) -> PreviewReport  # 干跑
#   _check_conflicts(moves) / _check_duplicates(moves) / _norm_path(p)
# =============================================================================

"""变更预览：从移动计划生成冲突、警告与摘要（干跑，不执行）。"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.core import metadata
from app.core.organizer import MovePlan
from app.core.scanner import ScannedFile

CONFLICT_COLLISION = "collision"  # 2+ 移动计划撞同一目标
CONFLICT_OCCUPIED = "occupied"    # 目标已被计划外文件占用
CONFLICT_MUTUAL = "mutual"        # 互换 / 成环：目标为另一待移动文件的源位置


@dataclass
class PreviewConflict:
    """一条冲突：涉及的移动计划被阻止执行。"""

    kind: str          # CONFLICT_* 之一
    target: Path
    moves: list[MovePlan]
    message: str       # 已格式化中文原因，界面直接展示


@dataclass
class PreviewReport:
    """一次干跑的完整结果。"""

    moves: list[MovePlan]           # 全部计划（含冲突行，界面逐行展示）
    conflicts: list[PreviewConflict]
    warnings: list[str]
    summary: dict                   # total / by_reason / conflict_count / blocked_count / warning_count

    @property
    def blocked_sources(self) -> set[Path]:
        """所有被冲突阻止的源文件路径。"""
        return {p.source for c in self.conflicts for p in c.moves}

    @property
    def safe_moves(self) -> list[MovePlan]:
        """可从执行的移动计划（Phase 7 应用时直接消费；派生，无状态漂移）。"""
        blocked = self.blocked_sources
        return [m for m in self.moves if m.source not in blocked]


def _norm_path(p: Path) -> str:
    """归一化绝对路径用于碰撞 / 归属比较（macOS/Windows 大小写不敏感）。"""
    s = str(Path(p).expanduser().resolve())
    return s.casefold() if sys.platform != "linux" else s


def _check_conflicts(moves: list[MovePlan]) -> list[PreviewConflict]:
    """检测三类冲突。目标已存在的 fs 检查是只读的（exists/is_symlink）。"""
    conflicts: list[PreviewConflict] = []

    # 1) collision：按归一化目标路径分组，同目标 ≥2 → 冲突
    by_target: dict[str, list[MovePlan]] = {}
    for m in moves:
        by_target.setdefault(_norm_path(m.target), []).append(m)
    collision_norms: set[str] = set()
    for target_norm, group in by_target.items():
        if len(group) >= 2:
            conflicts.append(PreviewConflict(
                kind=CONFLICT_COLLISION,
                target=group[0].target,
                moves=list(group),
                message=f"同名目标冲突：{len(group)} 个文件将移动到同一位置",
            ))
            collision_norms.add(target_norm)

    # 2) occupied / mutual：目标已存在
    source_by_norm = {_norm_path(m.source): m for m in moves}
    for m in moves:
        target_norm = _norm_path(m.target)
        if target_norm == _norm_path(m.source):
            continue  # build_plan 已跳过 target==source，这里防御
        t = m.target
        if not (t.exists() or t.is_symlink()):
            continue
        occupant = source_by_norm.get(target_norm)
        if occupant is not None and occupant is not m:
            conflicts.append(PreviewConflict(
                kind=CONFLICT_MUTUAL,
                target=t,
                moves=[m],
                message=f"目标位置将被另一待移动文件占用：{occupant.source.name}",
            ))
        elif target_norm not in collision_norms:
            conflicts.append(PreviewConflict(
                kind=CONFLICT_OCCUPIED,
                target=t,
                moves=[m],
                message=f"目标位置已被其他文件占用：{t.name}",
            ))

    conflicts.sort(key=lambda c: _norm_path(c.target))
    return conflicts


def _check_duplicates(moves: list[MovePlan]) -> list[str]:
    """检测待移动的源文件中是否存在内容重复（读取内容哈希，按大小门控）。

    源文件已消失（OSError）时跳过，不阻塞预览。
    """
    files: list[ScannedFile] = []
    for m in moves:
        try:
            files.append(ScannedFile.from_path(m.source))
        except OSError:
            continue
    warnings: list[str] = []
    for group in metadata.detect_duplicates(files):
        names = "、".join(f.name for f in sorted(group, key=lambda f: str(f.path)))
        warnings.append(f"检测到 {len(group)} 个内容重复的文件：{names}")
    return warnings


def generate_preview(
    moves: Iterable[MovePlan],
    *,
    extra_warnings: Iterable[str] = (),
) -> PreviewReport:
    """干跑：把移动计划转成预览报告。不触碰任何文件。

    ``extra_warnings`` 由调用方提供（如低置信度标签等需要 DB 的警告），
    保持本模块纯逻辑可测。返回的 ``report.safe_moves`` 可直接交给 Phase 7。
    """
    plans = sorted(moves, key=lambda plan: str(plan.source))
    conflicts = _check_conflicts(plans)
    warnings = list(extra_warnings) + _check_duplicates(plans)

    by_reason: dict[str, int] = {}
    for m in plans:
        by_reason[m.reason] = by_reason.get(m.reason, 0) + 1

    report = PreviewReport(
        moves=plans,
        conflicts=conflicts,
        warnings=warnings,
        summary={},
    )
    report.summary.update({
        "total": len(plans),
        "by_reason": dict(sorted(by_reason.items())),
        "conflict_count": len(conflicts),
        "blocked_count": len(report.blocked_sources),
        "warning_count": len(warnings),
    })
    return report
