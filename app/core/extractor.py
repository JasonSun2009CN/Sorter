# =============================================================================
# app/core/extractor.py —— 内容文本提取
#
# 作用：
#   从常见文档 / 图片中尽力提取纯文本，作为 ML 分类的输入特征。
#   解析失败或不可解析的文件返回 None，不影响主流程。
#
# 大致结构：
#   def extract_text(path) -> str | None     # 按扩展名分发解析器
#   def _extract_pdf(path) -> str            # PyMuPDF
#   def _extract_docx(path) -> str           # python-docx
#   def _extract_image(path) -> str | None   # Pillow（占位，MVP 可选）
# =============================================================================
