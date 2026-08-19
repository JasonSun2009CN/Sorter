# =============================================================================
# app/gui/main_window.py —— 主窗口
#
# 作用：
#   应用主窗口，工作流中枢。装配四个子视图并通过 QStackedWidget 切换，
#   同时在视图之间传递数据（扫描结果 → 标签 → 规则 → 预览 → 应用）。
#
# 大致结构：
#   class MainWindow(QMainWindow)
#       __init__(db)              # 创建主窗口与四个视图
#       _setup_menu()             # 菜单：打开目录 / 撤销 / 设置
#       _setup_stacked_widget()   # 视图容器
#       switch_view(index)        # 切换当前视图
#       on_scan_finished(files)   # 扫描完成回调，流转到 tag_view
#       on_rules_ready(rules)     # 规则就绪回调，流转到 preview_view
# =============================================================================
