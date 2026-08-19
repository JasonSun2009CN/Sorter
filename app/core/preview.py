# =============================================================================
# app/core/preview.py —— 变更预览 / 干跑
#
# 作用：
#   安全机制的落地实现。把组织计划渲染成清晰的 old→new 清单，
#   并做冲突、重复、低置信度等检查，产出可展示的预览报告。
#
# 大致结构：
#   @dataclass PreviewReport
#       moves: list[MovePlan] / conflicts / duplicates / warnings
#   def generate_preview(plan) -> PreviewReport  # 干跑，不触碰文件
#   def _check_conflicts(plan)                   # 重名冲突
#   def _check_duplicates(plan)                  # 重复文件
# =============================================================================
