# =============================================================================
# app/core/history.py —— 操作历史与撤销
#
# 作用：
#   每次组织操作生成一条可逆记录（旧路径 → 新路径），
#   支持撤销最后一次操作，尽量恢复文件原状。
#
# 大致结构：
#   @dataclass OperationRecord
#       id / timestamp / moves: list[(old, new)]
#   def record_operation(db, moves) -> OperationRecord  # 写入数据库
#   def undo_last(db) -> int                            # 回滚最近一次操作
#   def list_history(db) -> list[OperationRecord]
# =============================================================================
