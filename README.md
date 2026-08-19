# Sorter

A local-first personal file manager. Scans a folder, recognizes file content (OCR for images, text extraction for documents), generates a summary and auto-tags each file, then helps you organize — auto-planned or with your own rules — with a full preview before anything is moved, and undo after.

```text
扫描 → 识别内容（OCR/文档）→ 概述 + 自动标签 → 审核标签 → 自动/手动规划 → 预览 → 确认应用 → 撤销
```

All processing is local. No account, no cloud, no internet.

## 运行

```bash
python main.py        # 依赖见 pyproject.toml（uv sync）
```

数据库默认在 `~/.sorter/sorter.db`。

## 图片 OCR

图片文字识别使用 tesseract：

```bash
brew install tesseract            # 或其它系统的 tesseract 包
brew install tesseract-lang       # 可选：中文等更多语言（chi_sim）
```

- 未安装 tesseract → 图片静默跳过 OCR（不影响其它功能）。
- 已安装但缺 `chi_sim` → 中文图片用英文识别，应用内会提示一次。

## 测试

```bash
uv sync && python -m pytest tests/
```
