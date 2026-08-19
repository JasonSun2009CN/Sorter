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

from pathlib import Path
from typing import Iterable

from app.core import metadata
from app.core.organizer import MovePlan, _same_location, _sanitize_segment
from app.core.scanner import ScannedFile
from app.database import Database
from app.database.queries import get_tag_scores_by_path


def _best_tag(file: ScannedFile, scored: list[tuple[str, str, float]]) -> str | None:
    """挑选该文件的最佳归类标签：user > learned > 类型兜底。"""
    for tag, source, _ in scored:
        if source == "user":
            return tag
    for tag, source, _ in scored:
        if source == "learned":
            return tag
    type_tag = metadata.infer_type(file.extension)
    return type_tag if type_tag != "other" else None


def auto_plan(
    db: Database,
    files: Iterable[ScannedFile],
    root: "str | Path",
) -> list[MovePlan]:
    """按最佳标签为每个文件生成移动计划（只计划不执行）。

    - 无标签且类型为 other 的文件跳过（不动）；
    - 已位于目标位置（target == source）跳过，保证幂等；
    - 返回按 source 排序的 MovePlan 列表，可直接交给 generate_preview。
    """
    files = list(files)
    root = Path(root).expanduser().resolve()
    scores = get_tag_scores_by_path(db)
    plans: list[MovePlan] = []
    for f in files:
        best = _best_tag(f, scores.get(str(f.path), []))
        if best is None:
            continue
        segment = _sanitize_segment(best)
        target = root / segment / f.name
        if _same_location(f.path, target):
            continue
        plans.append(MovePlan(source=f.path, target=target, reason=segment))
    plans.sort(key=lambda p: str(p.source))
    return plans
