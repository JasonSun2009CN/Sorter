# =============================================================================
# app/gui/workers.py —— 后台工作线程
#
# 作用：
#   把耗时的扫描 / 标签计算放到 QThread 里跑，避免阻塞界面。
#
# 线程安全约束（重要）：
#   sqlite3 连接默认 check_same_thread=True，禁止跨线程共享 Database。
#   每个 Worker 在 run() 内自建一条连接（Database(db_path)），finally 中关闭；
#   UI 线程用自己的 Database 只读。WAL 模式保证跨连接并发安全。
#
#   sklearn 首次导入约 1–2s：TagWorker 在 run() 内延迟导入 app.core.tagging
#   （→ classifier → sklearn），绝不在 GUI 模块顶层导入。
#
# 结构：
#   class ScanWorker(QObject)   # 扫描 + 建索引 → finished(files)
#   class TagWorker(QObject)    # 系统/学习标签 → finished(files, n_sys, n_learn)
#   def start_worker(worker, owner) -> QThread  # QThread 装配脚手架
# =============================================================================

"""后台工作线程：扫描与标签计算。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Signal

if TYPE_CHECKING:
    from pathlib import Path


def start_worker(worker: QObject, owner: QObject) -> QThread:
    """把 worker 挪到新建 QThread 并启动，返回 thread（调用方需持有引用防 GC）。

    连接：started → run；finished/error → quit；finished → worker 释放；
    thread.finished → thread 释放。
    注意：worker 作为局部变量在调用方作用域结束后可能被 Python GC 回收，
    导致信号静默丢失 —— 这里把 worker 挂在 thread 上持有引用，线程结束时清除。
    """
    thread = QThread(owner)
    thread._worker = worker  # 持有引用，防止 GC 提前回收 worker
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    worker.error.connect(thread.quit)
    thread.finished.connect(thread.deleteLater)
    thread.finished.connect(lambda t=thread: setattr(t, "_worker", None))
    thread.start()
    return thread


def stop_thread(thread: QThread | None, timeout_ms: int = 3000) -> None:
    """安全停止一个工作线程并等待其结束（用于窗口关闭时的清理）。

    线程完成后可能已被 ``thread.finished`` → ``deleteLater`` 释放其 C++ 对象，
    此时 Python 包装对象仍然存活 —— 对这类僵尸引用做防御处理。
    """
    if thread is None:
        return
    try:
        if not thread.isRunning():
            return
        thread.quit()
        thread.wait(timeout_ms)
    except RuntimeError:
        pass  # C++ 对象已被删除，无需再停止


class ScanWorker(QObject):
    """递归扫描 + 写入索引，完成后发出 ScannedFile 列表。"""

    progress = Signal(str)
    progress_value = Signal(int)  # 0-100
    finished = Signal(list)  # list[ScannedFile]
    error = Signal(str)

    def __init__(self, db_path: "str | Path", root: "str | Path") -> None:
        super().__init__()
        self._db_path = str(db_path)
        self._root = str(root)

    def run(self) -> None:
        from app.core.scanner import Scanner
        from app.database import Database

        db = Database(self._db_path)
        try:
            self.progress.emit("正在扫描目录…")
            files = Scanner(db).scan_and_index(self._root, db)
            self.finished.emit(files)
        except Exception as exc:  # noqa: BLE001 —— 边界错误统一上报界面
            self.error.emit(str(exc))
        finally:
            db.close()


class TagWorker(QObject):
    """为已索引文件生成系统标签 + 内容关键词标签 + 概述 + 学习标签。"""

    progress = Signal(str)
    progress_value = Signal(int)  # 0-100
    finished = Signal(list, int, int, int, int)  # files, n_system, n_content, n_summary, n_learned
    error = Signal(str)

    def __init__(self, db_path: "str | Path", files: list) -> None:
        super().__init__()
        self._db_path = str(db_path)
        self._files = files

    def run(self) -> None:
        # 延迟导入：sklearn 首次导入较慢，留在此线程内完成
        from app.core.extractor import IMAGE_EXTS, extract_text, ocr_hint
        from app.core.summarizer import build_summaries
        from app.core.tagging import assign_content_tags, assign_learned_tags, assign_system_tags
        from app.database import Database
        from app.database.summaries import save_summaries

        db = Database(self._db_path)
        try:
            self.progress.emit("正在生成系统标签…")
            self.progress_value.emit(5)
            n_system = assign_system_tags(db, self._files)

            # 一次内容提取，供内容标签 / 概述 / ML 语料复用
            self.progress.emit("正在识别文件内容…")
            if any(f.extension in IMAGE_EXTS for f in self._files):
                hint = ocr_hint()
                if hint:
                    self.progress.emit(hint)
            texts: dict[str, str | None] = {}
            total = len(self._files)
            for i, f in enumerate(self._files):
                if i % 20 == 0:
                    self.progress.emit(f"正在识别文件内容… ({i}/{total})")
                    self.progress_value.emit(5 + int(i / total * 65) if total else 70)
                texts[str(f.path)] = extract_text(f.path)
            self.progress_value.emit(70)

            self.progress.emit("正在生成标签与概述…")
            n_content = assign_content_tags(db, self._files, texts=texts)
            n_summary = save_summaries(db, build_summaries(self._files, texts))
            self.progress_value.emit(85)
            self.progress.emit("正在预测学习标签…")
            n_learned = assign_learned_tags(db, self._files, texts=texts)
            self.progress_value.emit(100)
            self.finished.emit(self._files, n_system, n_content, n_summary, n_learned)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            db.close()


class ApplyWorker(QObject):
    """执行移动计划（纯文件操作，无需数据库连接）。"""

    finished = Signal(list, list)  # moved_pairs, errors
    error = Signal(str)

    def __init__(self, safe_moves: list) -> None:
        super().__init__()
        self._safe_moves = safe_moves

    def run(self) -> None:
        from app.core.organizer import apply_plan

        try:
            moved, errors = apply_plan(self._safe_moves)
            self.finished.emit(moved, errors)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class UndoWorker(QObject):
    """回滚最近一次操作（线程内自建数据库连接）。"""

    finished = Signal(object, list)  # OperationRecord | None, errors
    error = Signal(str)

    def __init__(self, db_path: "str | Path") -> None:
        super().__init__()
        self._db_path = str(db_path)

    def run(self) -> None:
        from app.core import history
        from app.database import Database

        db = Database(self._db_path)
        try:
            record, errors = history.undo_last(db)
            self.finished.emit(record, errors)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            db.close()
