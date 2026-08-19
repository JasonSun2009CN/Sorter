# =============================================================================
# app/core/organizer.py —— 组织引擎
#
# 作用：
#   根据用户规则为每个文件计算目标路径。本模块只“计划”不“执行”，
#   实际的移动发生在用户确认之后。
#
# 大致结构：
#   @dataclass MovePlan
#       source: Path / target: Path / reason: str
#   def build_plan(files, rules) -> list[MovePlan]  # 规则 → 目标路径
#   def apply_plan(plans) -> OperationRecord        # 实际移动（仅确认后）
#   def _resolve_conflicts(plans)                   # 重名 / 目标冲突处理
# =============================================================================
