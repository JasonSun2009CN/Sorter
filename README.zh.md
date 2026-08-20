# Sorter

> 🌐 **语言 / Language**: [English](README.md) · [中文](README.zh.md)

A **local-first** personal file organizer. Scan a folder, recognize what's inside (OCR for images, text extraction for documents), auto-summarize and auto-tag every file, then let the app organize them — automatically or under rules you define — with a full preview before anything moves and one-click undo afterwards.

```text
扫描 → 识别内容（OCR / 文档）→ 概述 + 自动标签 → 审核标签
   → 自动规划 / 手动规则 → 预览（树视图） → 确认应用 → 撤销
```

All processing happens on your machine. **No account, no cloud, no internet, no LLM API calls.**

---

## 目录

1. [功能特性](#功能特性)
2. [支持的格式](#支持的格式)
3. [系统要求](#系统要求)
4. [安装](#安装)
5. [运行](#运行)
6. [使用流程](#使用流程)
7. [标签体系](#标签体系)
8. [组织规则](#组织规则)
9. [安全与撤销](#安全与撤销)
10. [图片 OCR（Tesseract）](#图片-ocrtesseract)
11. [测试与开发](#测试与开发)
12. [项目结构](#项目结构)
13. [常见问题](#常见问题)

---

## 功能特性

| 模块 | 能力 |
| --- | --- |
| **扫描** | 递归遍历任意目录，自动过滤隐藏文件 / 系统目录；后台线程不阻塞 UI |
| **内容识别** | 纯文本 / 代码 / Markdown；PDF；Word；PowerPoint；Excel；图片 OCR；压缩包成员列表；音视频元数据 |
| **自动概述** | 从内容里抽关键词 + 首段，生成一句可读 summary |
| **自动标签** | 系统标签（按元数据确定性生成） + 学习标签（基于 TF-IDF 的本地分类器） |
| **标签审核** | 增删改用户标签；冲突时系统标签按首写获胜保持只读 |
| **自动规划** | 一键按「最佳标签 / 类型 / 年份 / 扩展名」生成多层文件夹结构 |
| **手动规则** | 任意组合 `tag / type / extension / year_created / year_modified` 维度，按目录层级建模 |
| **预览** | 旧路径 → 新路径树视图 + 冲突 / 重复 / 低置信度预警 |
| **安全应用** | 弹窗二次确认；不覆盖、不静默改名、不删除原文件 |
| **撤销** | 每次组织操作生成可逆记录，「编辑 → 撤销」一键回滚最近一次操作 |

---

## 支持的格式

| 类别 | 扩展名 |
| --- | --- |
| **文档** | `.pdf`, `.doc`, `.docx`, `.rtf`, `.odt`, `.pages` |
| **表格** | `.xls`, `.xlsx`, `.ods`, `.csv` |
| **演示** | `.ppt`, `.pptx`, `.key`, `.odp` |
| **图片（OCR）** | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`, `.tiff`, `.tif`, `.heic`, `.jfif` |
| **压缩包** | `.zip`, `.tar`, `.tgz`, `.gz`, `.bz2`, `.xz` |
| **音视频（仅元数据）** | `.mp3`, `.wav`, `.flac`, `.aac`, `.m4a`, `.ogg`, `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.m4v` |
| **纯文本 / 代码** | `.txt`, `.md`, `.markdown`, `.rst`, `.csv`, `.tsv`, `.log`, `.json`, `.xml`, `.html`, `.htm`, `.py`, `.js`, `.ts`, `.java`, `.c`, `.h`, `.cpp`, `.go`, `.rs`, `.yml`, `.yaml`, `.ini`, `.cfg`, `.toml`, `.sql` |

不可解析或二进制文件会被忽略但仍出现在扫描列表里（仅做路径 / 元数据索引）。

---

## 系统要求

- **操作系统**：macOS / Linux / Windows 均可
- **Python**：3.11 或更高（项目使用 `requires-python = ">=3.11"`）
- **磁盘**：几百 MB（依赖占大头的是 PyMuPDF + PySide6）
- **内存**：扫描 + ML 分类在后台线程跑，普通笔记本足够
- **可选**：
  - [Tesseract OCR](#图片-ocrtesseract) —— 图片文字识别
  - `tesseract-lang` / `chi_sim` 中文语言包

---

## 安装

仓库自带 `pyproject.toml` + `uv.lock`，**推荐用 [uv](https://docs.astral.sh/uv/)**：

```bash
# 1. 安装 uv（任选其一）
brew install uv                  # macOS
curl -LsSf https://astral.sh/uv/install.sh | sh   # 任意系统

# 2. 克隆并进入项目
git clone <repo-url> Sorter
cd Sorter

# 3. 同步依赖（自动创建 .venv 并写入 uv.lock 锁定的版本）
uv sync
```

不想用 uv 也可以用 pip：

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> `requirements.txt` 是 runtime 依赖的精简版；`pyproject.toml` 还声明了 `pytest` 等 dev 依赖。开发场景请用 `uv sync`。

### 可选：安装 Tesseract（OCR）

图片里的文字识别走 Tesseract；不装也能用，只是图片静默跳过 OCR。

```bash
# macOS
brew install tesseract
brew install tesseract-lang       # 中文 + 多语言（含 chi_sim）

# Ubuntu / Debian
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-chi-sim

# Windows
# 从 https://github.com/UB-Mannheim/tesseract/wiki 下载安装包，
# 并把 tesseract.exe 所在目录加到 PATH
```

详见 [图片 OCR](#图片-ocrtesseract)。

---

## 运行

```bash
# uv
uv run python main.py

# 经典 venv
source .venv/bin/activate
python main.py
```

启动后：

1. **菜单 → 文件 → 打开目录…** 选一个要整理的文件夹
2. 四个工作流视图依次推进：扫描 → 标签审核 → 规则（可选）→ 预览
3. 应用前一定会经过变更预览 + 二次确认

数据库默认位置：

```text
~/.sorter/sorter.db
```

想换位置可以直接改 `main.py` 里 `_default_db_path()`。

### 菜单速览

| 菜单 | 项 | 作用 |
| --- | --- | --- |
| 文件 | 打开目录… | 选择扫描根目录 |
| 文件 | 退出 | 关闭应用 |
| 编辑 | 撤销 | 恢复上一次组织操作（成功后菜单项自动启用） |
| 组织 | 手动规则… | 打开规则编辑器（高级） |
| 帮助 | 关于 | 版本 / 设计理念 |

---

## 使用流程

#### ① 扫描

后台线程递归遍历目录，按 `os.stat` 收集 size / mtime / ctime，并写入 SQLite。隐藏文件与系统目录自动跳过。

#### ② 内容识别

对每个文件尽力提取纯文本 + 元数据：

- 纯文本 / 代码：直接按 UTF-8 读（`errors="replace"` 兜底）
- PDF / Word / PPT / Excel：各用对应库逐页 / 逐段抽取
- 图片：Tesseract OCR
- 压缩包：枚举成员名
- 音视频：用 `mutagen` 读元数据（无文本）

失败或不支持 → 返回 `None` / `{}`，**绝不抛异常打断主流程**。

#### ③ 概述 + 标签

- **概述**：从提取出的文本里抽首段 + 关键词评分
- **系统标签**：扩展名 → `pdf` / `image` / `archive` / ...；大小 ≥ 100 MiB → `large-file`；30 天内修改 → `recently-modified`；内容哈希重复 → `duplicate`；父目录名
- **学习标签**：基于「用户修正样本」训练的 TF-IDF + 线性分类器（详见 `app/ml/`）

#### ④ 标签审核

可对任意文件增删改用户标签。系统标签作为只读 chip 展示，用户标签与系统标签冲突时**首写获胜**（避免反复覆盖）。

#### ⑤ 自动规划 / 手动规则

- **自动规划**（默认）：选「按标签 + 类型」两个维度，按每文件最佳标签（user > learned > 类型）生成多层文件夹
- **手动规则**：用「组织 → 手动规则…」打开规则编辑器，把 `tag / type / extension / year_created / year_modified` 任意维度按目录层级排列

#### ⑥ 预览

可视化「旧路径 → 新路径」树视图，提示：

- 文件名冲突
- 内容重复
- 低置信度标签

#### ⑦ 应用 + 撤销

- 预览点「应用变更」→ 弹窗二次确认 → 后台线程移动文件 → 写一条可逆记录
- 「编辑 → 撤销」一键回滚最近一次操作（失败的恢复在弹窗里逐条提示）

---

## 标签体系

| 来源 | 示例 | 谁写的 |
| --- | --- | --- |
| **系统标签**（只读） | `pdf`, `image`, `archive`, `large-file`, `recently-modified`, `duplicate` | 程序按元数据确定性生成 |
| **学习标签** | `mathematics`, `physics`, `finance`, `travel` | 本地 ML 分类器 |
| **用户标签** | `important`, `semester-1`, `MIT` | 你在标签审核视图里手动加 |

概念层级：

```text
File
 ├── System Tags
 ├── Learned Tags
 └── User Tags
```

---

## 组织规则

规则 = 按顺序求值的目录层级列表。支持五种维度：

| `kind` | 行为 | 失败兜底 |
| --- | --- | --- |
| `tag` | 文件必须拥有该标签；目录段 = 清洗后的标签名 | 文件无标签 → 整条规则不适用，文件不动 |
| `type` | 扩展名 → 类别（pdf / image / ...） | 类别 `other` → 跳到下一层 |
| `extension` | 按扩展名 | 空扩展名 → 跳过 |
| `year_created` | 创建年份 | 时间戳缺失 → 跳过 |
| `year_modified` | 修改年份 | 时间戳缺失 → 跳过 |

**整体规则 = all-or-nothing**：任一 `tag` 层缺失 → 该文件不动；其它维度缺失只跳过该层目录。

目录段清洗：去除控制字符、空段 → `其他` / `未知` 兜底，避免空目录名。

---

## 安全与撤销

| 不做 | 说明 |
| --- | --- |
| ❌ 静默覆盖 | 同名冲突会进 `unsafe_moves`，预览里高亮，**默认不进应用列表** |
| ❌ 静默改名 | 不存在 |
| ❌ 静默删除 | 不存在 |

每次「应用变更」成功都会写一条 `operations` 记录（`old` → `new`），点「编辑 → 撤销」触发回滚。撤销语义：

- 逐文件尝试恢复到 `old` 路径
- 个别恢复失败 → 记录标记为已撤销（避免阻塞更早的操作），失败原因在弹窗里逐条提示
- 记录全空 → 撤销按钮自动置灰

---

## 图片 OCR（Tesseract）

- **未安装 tesseract** → 图片静默跳过 OCR（其它功能不受影响）
- **已装但缺 `chi_sim`** → 中文图片用英文识别，应用内启动时弹一次提示
- **完全装好** → 中英文双语识别，识别结果进内容特征和概述

自动检测路径：先 `shutil.which("tesseract")`，再兜底常见安装目录（`/opt/homebrew/bin`、`/usr/local/bin`、`/usr/bin`）。

---

## 测试与开发

```bash
# 安装 dev 依赖（uv 会自动拉 pytest）
uv sync

# 跑全部测试
uv run python -m pytest tests/

# 单跑某个文件
uv run python -m pytest tests/test_scanner.py -q

# 看覆盖率
uv run python -m pytest tests/ --cov=app
```

测试覆盖：

- `tests/test_scanner.py` — 递归扫描、过滤
- `tests/test_extractor.py` / `test_extractor_content.py` — 各格式文本提取
- `tests/test_tagging_learned.py` / `test_classifier.py` / `test_features.py` / `test_training.py` — ML 管线
- `tests/test_summarizer.py` / `test_summaries_db.py` — 概述生成
- `tests/test_rules.py` / `test_organizer.py` / `test_preview.py` / `test_history.py` — 组织 / 预览 / 撤销
- `tests/test_gui_smoke.py` / `test_preview_view.py` / `test_formatting.py` — GUI 烟测

CI 友好：纯 `pytest`，无外部服务依赖；ML 用确定性小样本。

---

## 项目结构

```text
Sorter/
├── main.py                       # 入口
├── pyproject.toml                # 项目元数据 + 依赖
├── uv.lock                       # 锁定的依赖版本
├── requirements.txt              # runtime 依赖（精简版）
├── app/
│   ├── core/                     # 业务核心
│   │   ├── scanner.py            #   文件扫描
│   │   ├── metadata.py           #   元数据 + 重复检测
│   │   ├── extractor.py          #   文本 / 元数据提取（含 OCR）
│   │   ├── tagging.py            #   系统 + 学习标签
│   │   ├── summarizer.py         #   自动概述
│   │   ├── organizer.py          #   规则模型 + 安全移动
│   │   ├── autoplan.py           #   自动规划
│   │   ├── preview.py            #   预览生成（冲突 / 重复检测）
│   │   └── history.py            #   操作记录 + 撤销
│   ├── ml/                       # 本地机器学习
│   │   ├── features.py           #   TF-IDF 特征
│   │   ├── classifier.py         #   线性分类器
│   │   └── training.py           #   用户修正样本训练
│   ├── database/                 # SQLite 访问层
│   │   ├── database.py           #   连接 + CRUD
│   │   ├── models.py             #   表结构
│   │   ├── queries.py            #   业务查询
│   │   ├── rules.py              #   组织规则持久化
│   │   └── summaries.py          #   概述持久化
│   └── gui/                      # PySide6 界面
│       ├── main_window.py        #   主窗口（工作流中枢）
│       ├── scan_view.py          #   ① 扫描
│       ├── tag_view.py           #   ② 标签审核
│       ├── rules_view.py         #   ③ 规则编辑器
│       ├── preview_view.py       #   ④ 预览
│       ├── workers.py            #   后台线程
│       ├── widgets.py            #   复用 widget
│       ├── theme.py              #   扁平 Fusion 主题
│       └── formatting.py         #   时间 / 大小格式化
└── tests/                        # pytest 测试集
```

---

## 常见问题

**Q：扫描后我的 PDF 没被识别成 `pdf` 标签？**
A：检查扩展名是否正确（必须小写且带 `.`，例如 `.PDF` 会被归一化为 `.pdf`）。实在不行看 `~/.sorter/sorter.db` 的 `files` 表。

**Q：撤销按钮是灰的？**
A：还没执行过「应用变更」，或者最近一次操作已经撤销过了。撤销只回滚最近一次。

**Q：中文图片 OCR 不准？**
A：需要 `tesseract-lang`（macOS）或 `tesseract-ocr-chi-sim`（Ubuntu）。详见上文 OCR 安装一节。

**Q：可以远程用吗？**
A：不能，也不打算支持。设计就是**纯本机** —— 不开端口、不联网、不上传文件。

**Q：数据库能换位置吗？**
A：可以。改 `main.py` 的 `_default_db_path()` 即可。

**Q：会动我没选中的文件吗？**
A：不会。只会移动扫描根目录下的文件；新目录在根目录内创建；同名冲突默认不进应用列表。

---

## 设计哲学（摘自 `PROJECT.md`）

> Machine understands the files.
> User defines the organization.
> Application previews the changes.
> User approves the operation.
> Application safely applies the changes.

ML 只负责「这是什么文件」，目录结构永远由你来定 —— 自动规划也只是一个默认值，可以随时改回手动规则。

---

## 许可

见 `LICENSE`。
