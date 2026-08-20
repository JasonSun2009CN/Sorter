# Sorter

> 🌐 **Language / 语言**: [English](README.md) · [中文](README.zh.md)

A **local-first** personal file organizer. Scan a folder, recognize what's inside (OCR for images, text extraction for documents), auto-summarize and auto-tag every file, then let the app organize them — automatically or under rules you define — with a full preview before anything moves and one-click undo afterwards.

```text
Scan → Recognize content (OCR / documents) → Summarize + auto-tag → Review tags
   → Auto-plan / manual rules → Preview (tree view) → Confirm & apply → Undo
```

All processing happens on your machine. **No account, no cloud, no internet, no LLM API calls.**

---

## Table of Contents

1. [Features](#features)
2. [Supported Formats](#supported-formats)
3. [System Requirements](#system-requirements)
4. [Installation](#installation)
5. [Running](#running)
6. [Workflow](#workflow)
7. [Tag System](#tag-system)
8. [Organization Rules](#organization-rules)
9. [Safety & Undo](#safety--undo)
10. [Image OCR (Tesseract)](#image-ocr-tesseract)
11. [Testing & Development](#testing--development)
12. [Project Layout](#project-layout)
13. [FAQ](#faq)

---

## Features

| Module | Capability |
| --- | --- |
| **Scan** | Recursively walk any folder; auto-skip hidden files / system dirs; runs in a background thread, never blocks the UI |
| **Content Recognition** | Plain text / code / Markdown; PDF; Word; PowerPoint; Excel; image OCR; archive member listings; audio/video metadata |
| **Auto-Summary** | Pulls leading paragraph + keywords from extracted text to produce a one-line summary |
| **Auto-Tag** | System tags (deterministic from metadata) + learned tags (local TF-IDF classifier) |
| **Tag Review** | Add / remove / edit user tags; on conflict, first-write wins so system tags stay read-only |
| **Auto-Plan** | One click generates multi-level folder layout from "best tag / type / year / extension" |
| **Manual Rules** | Compose `tag / type / extension / year_created / year_modified` dimensions in any order as directory levels |
| **Preview** | Old path → new path tree view + conflict / duplicate / low-confidence warnings |
| **Safe Apply** | Confirmation dialog before moving; never overwrites, never silently renames, never deletes source files |
| **Undo** | Every organization operation creates a reversible record; **Edit → Undo** restores the last operation with one click |

---

## Supported Formats

| Category | Extensions |
| --- | --- |
| **Documents** | `.pdf`, `.doc`, `.docx`, `.rtf`, `.odt`, `.pages` |
| **Spreadsheets** | `.xls`, `.xlsx`, `.ods`, `.csv` |
| **Presentations** | `.ppt`, `.pptx`, `.key`, `.odp` |
| **Images (OCR)** | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`, `.tiff`, `.tif`, `.heic`, `.jfif` |
| **Archives** | `.zip`, `.tar`, `.tgz`, `.gz`, `.bz2`, `.xz` |
| **Audio / Video (metadata only)** | `.mp3`, `.wav`, `.flac`, `.aac`, `.m4a`, `.ogg`, `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.m4v` |
| **Plain text / code** | `.txt`, `.md`, `.markdown`, `.rst`, `.csv`, `.tsv`, `.log`, `.json`, `.xml`, `.html`, `.htm`, `.py`, `.js`, `.ts`, `.java`, `.c`, `.h`, `.cpp`, `.go`, `.rs`, `.yml`, `.yaml`, `.ini`, `.cfg`, `.toml`, `.sql` |

Unparseable or binary files are silently ignored for content extraction but still appear in the scan list (path / metadata only).

---

## System Requirements

- **OS**: macOS / Linux / Windows
- **Python**: 3.11 or newer (`requires-python = ">=3.11"`)
- **Disk**: a few hundred MB (PyMuPDF + PySide6 are the biggest)
- **RAM**: scan + ML classification run on a background thread; any modern laptop is enough
- **Optional**:
  - [Tesseract OCR](#image-ocr-tesseract) — for image text recognition
  - `tesseract-lang` / `chi_sim` Chinese language pack

---

## Installation

The repo ships with `pyproject.toml` + `uv.lock`. **[uv](https://docs.astral.sh/uv/) is recommended**:

```bash
# 1. Install uv (pick one)
brew install uv                                       # macOS
curl -LsSf https://astral.sh/uv/install.sh | sh       # any OS

# 2. Clone and enter the project
git clone <repo-url> Sorter
cd Sorter

# 3. Sync dependencies (creates .venv and pins to uv.lock)
uv sync
```

If you prefer plain pip:

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> `requirements.txt` is a slim runtime-only list. `pyproject.toml` also declares dev deps (e.g. `pytest`). For dev work, use `uv sync`.

### Optional: install Tesseract (OCR)

Image text recognition goes through Tesseract. Without it the rest of the app still works — images simply skip OCR silently.

```bash
# macOS
brew install tesseract
brew install tesseract-lang       # Chinese + other langs (incl. chi_sim)

# Ubuntu / Debian
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-chi-sim

# Windows
# Download from https://github.com/UB-Mannheim/tesseract/wiki
# and add the tesseract.exe directory to PATH
```

See [Image OCR (Tesseract)](#image-ocr-tesseract) for details.

---

## Running

```bash
# uv
uv run python main.py

# plain venv
source .venv/bin/activate
python main.py
```

After launch:

1. **Menu → File → Open Folder…** pick the folder you want to organize
2. The four workflow views advance in turn: Scan → Tag Review → Rules (optional) → Preview
3. Files only move after the preview step + a confirmation dialog

Default database location:

```text
~/.sorter/sorter.db
```

To relocate it, edit `_default_db_path()` in `main.py`.

### Menu Cheat Sheet

| Menu | Item | Effect |
| --- | --- | --- |
| File | Open Folder… | Choose scan root |
| File | Quit | Close the app |
| Edit | Undo | Restore the last organization operation (the menu item auto-enables when one is available) |
| Organize | Manual Rules… | Open the rule editor (advanced) |
| Help | About | Version / design notes |

---

## Workflow

#### ① Scan

A background thread recursively walks the directory, collects `size / mtime / ctime` from `os.stat`, and writes everything to SQLite. Hidden files and system directories are filtered out automatically.

#### ② Content Recognition

For each file we do our best to extract plain text + structured metadata:

- **Plain text / code**: read as UTF-8 (`errors="replace"` as a safety net)
- **PDF / Word / PPT / Excel**: corresponding library extracts page-by-page / element-by-element
- **Images**: Tesseract OCR
- **Archives**: enumerate member names
- **Audio / video**: metadata via `mutagen` (no transcript)

Failure or unsupported → return `None` / `{}`. **Never raises into the main flow.**

#### ③ Summary + Tags

- **Summary**: leading paragraph + keyword scoring from the extracted text
- **System tags**: extension → `pdf` / `image` / `archive` / ...; size ≥ 100 MiB → `large-file`; modified within 30 days → `recently-modified`; duplicate content hash → `duplicate`; parent directory name
- **Learned tags**: a TF-IDF + linear classifier trained on user-correction samples (see `app/ml/`)

#### ④ Tag Review

Add / remove / edit user tags per file. System tags show as read-only chips. When a user tag collides with a system tag, **first-write wins** to avoid thrash on re-render.

#### ⑤ Auto-Plan / Manual Rules

- **Auto-plan** (default): pick "tag + type" dimensions; each file's best tag (user > learned > type) becomes its folder
- **Manual rules**: open via **Organize → Manual Rules…**; stack `tag / type / extension / year_created / year_modified` as directory levels

#### ⑥ Preview

Tree-view of "old path → new path" with warnings:

- Filename conflicts
- Duplicate content
- Low-confidence tags

#### ⑦ Apply + Undo

- Click **Apply Changes** in the preview → confirmation dialog → background thread moves files → a reversible record is written
- **Edit → Undo** rolls back the most recent operation; partial failures are listed in a dialog

---

## Tag System

| Source | Examples | Who writes |
| --- | --- | --- |
| **System tags** (read-only) | `pdf`, `image`, `archive`, `large-file`, `recently-modified`, `duplicate` | The program, deterministically from metadata |
| **Learned tags** | `mathematics`, `physics`, `finance`, `travel` | Local ML classifier |
| **User tags** | `important`, `semester-1`, `MIT` | You, in the Tag Review view |

Conceptually:

```text
File
 ├── System Tags
 ├── Learned Tags
 └── User Tags
```

---

## Organization Rules

A rule is an ordered list of directory levels. Five dimensions are supported:

| `kind` | Behavior | Failure fallback |
| --- | --- | --- |
| `tag` | File must have this tag; segment = sanitized tag name | No tag → rule does not apply, file stays put |
| `type` | Extension → category (pdf / image / ...) | Category `other` → drop this level |
| `extension` | By extension | Empty ext → drop this level |
| `year_created` | Year of creation | Missing timestamp → drop this level |
| `year_modified` | Year of modification | Missing timestamp → drop this level |

**The whole rule is all-or-nothing for `tag`**: if any `tag` level is missing, the file is not moved. Missing non-`tag` levels only drop that directory layer.

Segment sanitization: strips control characters and empty parts; falls back to `其他` / `未知` (`Other` / `Unknown`) to avoid empty folder names.

---

## Safety & Undo

| Never does | Why |
| --- | --- |
| ❌ Silently overwrite | Same-name conflicts land in `unsafe_moves`, highlighted in the preview, **excluded from apply by default** |
| ❌ Silently rename | Not implemented |
| ❌ Silently delete | Not implemented |

Every successful **Apply Changes** writes an `operations` row (`old` → `new`). **Edit → Undo** triggers a rollback:

- Try to restore each file to its `old` path
- On partial failure the record is still marked as undone (so it doesn't block earlier operations); failures are surfaced in a dialog
- When no records remain, the Undo button auto-disables

---

## Image OCR (Tesseract)

- **Tesseract not installed** → images silently skip OCR (everything else keeps working)
- **Installed but `chi_sim` missing** → Chinese images fall back to English recognition; a one-time hint is shown at startup
- **Fully installed** → bilingual recognition feeds content features and the summary

Auto-detect path: `shutil.which("tesseract")` first, then fallback common install dirs (`/opt/homebrew/bin`, `/usr/local/bin`, `/usr/bin`).

---

## Testing & Development

```bash
# Install dev dependencies (uv pulls pytest automatically)
uv sync

# Run all tests
uv run python -m pytest tests/

# Single file
uv run python -m pytest tests/test_scanner.py -q

# With coverage
uv run python -m pytest tests/ --cov=app
```

Test coverage:

- `tests/test_scanner.py` — recursive scan, filtering
- `tests/test_extractor.py` / `test_extractor_content.py` — per-format text extraction
- `tests/test_tagging_learned.py` / `test_classifier.py` / `test_features.py` / `test_training.py` — ML pipeline
- `tests/test_summarizer.py` / `test_summaries_db.py` — summary generation
- `tests/test_rules.py` / `test_organizer.py` / `test_preview.py` / `test_history.py` — organization / preview / undo
- `tests/test_gui_smoke.py` / `test_preview_view.py` / `test_formatting.py` — GUI smoke tests

CI-friendly: plain `pytest`, no external services; ML uses deterministic small samples.

---

## Project Layout

```text
Sorter/
├── main.py                       # Entry point
├── pyproject.toml                # Project metadata + deps
├── uv.lock                       # Locked dependency versions
├── requirements.txt              # Runtime deps (slim)
├── README.md                     # English (this file)
├── README.zh.md                  # 中文
├── app/
│   ├── core/                     # Business core
│   │   ├── scanner.py            #   File scan
│   │   ├── metadata.py           #   Metadata + duplicate detection
│   │   ├── extractor.py          #   Text / metadata extraction (incl. OCR)
│   │   ├── tagging.py            #   System + learned tags
│   │   ├── summarizer.py         #   Auto summary
│   │   ├── organizer.py          #   Rule model + safe move
│   │   ├── autoplan.py           #   Auto-plan
│   │   ├── preview.py            #   Preview generation (conflicts / duplicates)
│   │   └── history.py            #   Operation records + undo
│   ├── ml/                       # Local machine learning
│   │   ├── features.py           #   TF-IDF features
│   │   ├── classifier.py         #   Linear classifier
│   │   └── training.py           #   Train on user-correction samples
│   ├── database/                 # SQLite access layer
│   │   ├── database.py           #   Connection + CRUD
│   │   ├── models.py             #   Table schemas
│   │   ├── queries.py            #   Business queries
│   │   ├── rules.py              #   Persisted organization rules
│   │   └── summaries.py          #   Persisted summaries
│   └── gui/                      # PySide6 UI
│       ├── main_window.py        #   Main window (workflow hub)
│       ├── scan_view.py          #   ① Scan
│       ├── tag_view.py           #   ② Tag review
│       ├── rules_view.py         #   ③ Rule editor
│       ├── preview_view.py       #   ④ Preview
│       ├── workers.py            #   Background threads
│       ├── widgets.py            #   Reusable widgets
│       ├── theme.py              #   Flat Fusion theme
│       └── formatting.py         #   Time / size formatting
└── tests/                        # pytest suite
```

---

## FAQ

**Q: My PDF wasn't tagged `pdf` after the scan.**
A: Check that the extension is correct (lowercase, with a leading dot; `.PDF` is normalized to `.pdf`). You can also inspect the `files` table in `~/.sorter/sorter.db`.

**Q: The Undo button is greyed out.**
A: Either no **Apply Changes** has succeeded yet, or the most recent one has already been undone. Undo only rolls back the latest operation.

**Q: OCR on Chinese images is inaccurate.**
A: You need `tesseract-lang` (macOS) or `tesseract-ocr-chi-sim` (Ubuntu). See the OCR installation section above.

**Q: Can I use this remotely?**
A: No, and there are no plans to support it. The design is **strictly local** — no open ports, no network calls, no file uploads.

**Q: Can I move the database?**
A: Yes. Edit `_default_db_path()` in `main.py`.

**Q: Will it touch files I didn't select?**
A: No. Only files inside the scan root are moved; new folders are created inside the root; same-name conflicts default to "not in the apply list".

---

## Design Philosophy (excerpt from `PROJECT.md`)

> Machine understands the files.
> User defines the organization.
> Application previews the changes.
> User approves the operation.
> Application safely applies the changes.

ML only answers "what is this file?"; the directory structure is always yours to decide — auto-plan is just a sensible default you can swap for manual rules at any time.

---

## License

See `LICENSE`.
