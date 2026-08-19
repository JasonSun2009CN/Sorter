# =============================================================================
# app/gui/rules_view.py —— 组织规则视图（工作流步骤 ③）
#
# 作用：
#   让用户定义“文件如何被组织”，规则形如：属性 → 目录层级。
#   例：Subject → File Type；Year → Extension；Custom Tag → Directory。
#
# 大致结构：
#   class RulesView(QWidget)
#       _build_ui()               # 规则列表 + 规则编辑器
#       add_rule()                # 新增一条规则
#       edit_rule(rule)           # 编辑已有规则
#       remove_rule(rule)         # 删除规则
#       rules_changed()           # 规则变更信号（交给 MainWindow 流转）
# =============================================================================
