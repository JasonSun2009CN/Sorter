# =============================================================================
# app.core —— 核心业务逻辑
#
# 作用：
#   不依赖 UI 的纯业务层，可独立测试。按数据流依次为：
#   scanner → metadata / extractor → organizer → preview → history
#
# 模块：
#   scanner    文件扫描（递归遍历 + 建索引）
#   metadata   元数据提取（大小、时间、扩展名、重复检测）
#   extractor  内容文本提取（PDF / DOCX / 图片）
#   organizer  组织引擎（规则 → 目标路径，不实际移动）
#   preview    变更预览（old→new、冲突、警告）
#   history    操作历史与撤销
# =============================================================================

from app.core.scanner import ScannedFile, Scanner

__all__ = ["ScannedFile", "Scanner"]
