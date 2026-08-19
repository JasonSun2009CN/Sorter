# =============================================================================
# app/core/autoplan.py —— 自动规划整理（Phase：内容识别后）
#
# 作用：
#   不靠用户手动搭规则，直接根据每个文件的最佳标签生成移动计划：
#     优先级  user（用户明确加的）> learned（内容/ML 预测）> 类型（兜底）
#   类型兜底只取 infer_type 的类别标签，不用 large-file / duplicate / 目录名，
#   避免生成垃圾目录。选出的标签经 _sanitize_segment 清洗为目录段。
#
#   注意：Rule 模型是"文件必须拥有该标签才适用"，无法表达"每个文件按自己的
#   最佳标签归类"，所以自动规划直接产出 MovePlan（与 build_plan 同一产物，
#   下游 preview / apply 流程完全复用）。
#
# 结构：
#   _best_tag(file, scored) -> str | None
#   auto_plan(db, files, root) -> list[MovePlan]
# =============================================================================

"""自动规划：按每文件最佳标签生成组织计划。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.core import metadata
from app.core.organizer import MovePlan, _same_location, _sanitize_segment
from app.core.scanner import ScannedFile
from app.database import Database
from app.database.queries import get_tag_scores_by_path


DIM_TAG = "tag"
DIM_TYPE = "type"
DIM_YEAR = "year"
DIM_EXTENSION = "extension"
DIMENSIONS: tuple[str, ...] = (DIM_TAG, DIM_TYPE, DIM_YEAR, DIM_EXTENSION)


def _best_tag(_file: ScannedFile, scored: list[tuple[str, str, float]]) -> str | None:
    """挑选该文件的最佳归类标签：user > learned；否则返回 None（由 DIM_TYPE 兜底）。"""
    for tag, source, _ in scored:
        if source == "user":
            return tag
    for tag, source, _ in scored:
        if source == "learned":
            return tag
    return None


def _segment_for(
    file: ScannedFile,
    dimension: str,
    scored: list[tuple[str, str, float]],
) -> str | None:
    """按单个分类维度计算目录段；该维度无值返回 None。"""
    if dimension == DIM_TAG:
        best = _best_tag(file, scored)
        return _sanitize_segment(best) if best else None
    if dimension == DIM_TYPE:
        type_tag = metadata.infer_type(file.extension)
        return type_tag if type_tag != "other" else None
    if dimension == DIM_YEAR:
        if file.mtime <= 0:
            return None
        return str(datetime.fromtimestamp(file.mtime).year)
    if dimension == DIM_EXTENSION:
        ext = file.extension.upper().lstrip(".")
        return ext or None
    return None


def auto_plan(
    db: Database,
    files: Iterable[ScannedFile],
    root: "str | Path",
    *,
    dimensions: Iterable[str] = (DIM_TAG, DIM_TYPE),
) -> list[MovePlan]:
    """按所选分类维度（顺序 = 目录层级）为每个文件生成移动计划。

    - 每个文件逐维度计算目录段，缺失的维度跳过 → 单层/多层天然混合；
    - 没有任何段（如无标签且类型 other）→ 跳过（不动）；
    - 已位于目标位置（target == source）跳过，保证幂等；
    - 返回按 source 排序的 MovePlan 列表，可直接交给 generate_preview。
    """
    files = list(files)
    root = Path(root).expanduser().resolve()
    dims = [d for d in dimensions if d in DIMENSIONS]
    scores = get_tag_scores_by_path(db)
    plans: list[MovePlan] = []
    for f in files:
        scored = scores.get(str(f.path), [])
        segments: list[str] = [
            s for s in (_segment_for(f, d, scored) for d in dims) if s
        ]
        if not segments:
            continue
        target = root.joinpath(*segments) / f.name
        if _same_location(f.path, target):
            continue
        plans.append(MovePlan(source=f.path, target=target, reason="/".join(segments)))
    plans.sort(key=lambda p: str(p.source))
    return plans
