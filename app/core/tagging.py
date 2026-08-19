# =============================================================================
# app/core/tagging.py —— 标签生成与持久化（Phase 2 + Phase 3）
#
# 作用：
#   - 确定性系统标签（Phase 2）：基于元数据生成 —— 类型（pdf / image /
#     archive ...）、大文件、最近修改、重复、所属目录。
#   - 学习标签（Phase 3）：基于用户修正样本训练分类器，为文件预测
#     learned 标签并附置信度。
#
# 结构：
#   TAG_LARGE_FILE / TAG_RECENTLY_MODIFIED / TAG_DUPLICATE ...
#   def compute_system_tags(f, *, duplicate, ...) -> list[str]  # 纯计算
#   def assign_system_tags(db, files) -> int                    # 计算 + 写库
#   def assign_learned_tags(db, files) -> int                   # ML 预测 + 写库
#   def _ensure_tag(conn, name, kind) -> int                    # 幂等写 tags
# =============================================================================

"""系统标签生成 + 学习标签预测的入口。"""

from __future__ import annotations

import sqlite3
from typing import Iterable

from app.core import metadata
from app.core.extractor import extract_text
from app.core.scanner import ScannedFile
from app.core.summarizer import keyword_scores
from app.database import Database
from app.ml.classifier import TagClassifier
from app.ml.features import build_corpus, make_vectorizer
from app.ml.training import load_training_data

# 系统标签名常量
TAG_LARGE_FILE = "large-file"
TAG_RECENTLY_MODIFIED = "recently-modified"
TAG_DUPLICATE = "duplicate"

# 判定阈值
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100 MiB
RECENT_DAYS = 30

# 系统标签词汇：内容关键词与之冲突时跳过（tags.kind 首写获胜会变只读系统 chip）
SYSTEM_TAG_NAMES: frozenset[str] = frozenset(
    set(metadata.EXTENSION_TYPES.values())
    | {TAG_LARGE_FILE, TAG_RECENTLY_MODIFIED, TAG_DUPLICATE}
)


def compute_system_tags(
    file: ScannedFile,
    *,
    duplicate: bool = False,
    large_threshold: int = LARGE_FILE_THRESHOLD,
    recent_days: int = RECENT_DAYS,
) -> list[str]:
    """为单个文件计算确定性系统标签（纯计算，不访问数据库）。"""
    tags: set[str] = set()

    # 类型标签（pdf / image / archive ...），other 不产生标签
    type_tag = metadata.infer_type(file.extension)
    if type_tag != "other":
        tags.add(type_tag)

    if file.size >= large_threshold:
        tags.add(TAG_LARGE_FILE)
    if metadata.is_recently_modified(file.mtime, recent_days):
        tags.add(TAG_RECENTLY_MODIFIED)
    if duplicate:
        tags.add(TAG_DUPLICATE)

    # 所属目录标签（直接父目录名）
    parent = file.path.parent.name
    if parent:
        tags.add(parent)

    return sorted(tags)


def _duplicate_paths(files: Iterable[ScannedFile]) -> set[str]:
    """返回所有属于重复组的文件绝对路径集合。"""
    dup_paths: set[str] = set()
    for group in metadata.detect_duplicates(files):
        for f in group:
            dup_paths.add(str(f.path))
    return dup_paths


def _ensure_tag(conn: sqlite3.Connection, name: str, kind: str = "system") -> int:
    """确保标签存在并返回其 id（幂等）。"""
    conn.execute(
        "INSERT OR IGNORE INTO tags (name, kind) VALUES (?, ?)", (name, kind)
    )
    row = conn.execute(
        "SELECT id FROM tags WHERE name = ?", (name,)
    ).fetchone()
    return row["id"] if row else 0


def assign_system_tags(
    db: Database,
    files: Iterable[ScannedFile],
    *,
    large_threshold: int = LARGE_FILE_THRESHOLD,
    recent_days: int = RECENT_DAYS,
) -> int:
    """为已索引文件计算系统标签并写入 tags / file_tags（单个事务）。

    返回写入的 file_tags 关联条数；未在数据库中索引到的文件会被跳过。
    """
    files = list(files)
    dup_paths = _duplicate_paths(files)
    written = 0
    with db.transaction() as conn:
        for f in files:
            row = conn.execute(
                "SELECT id FROM files WHERE path = ?", (str(f.path),)
            ).fetchone()
            if row is None:
                continue  # 未索引，跳过
            tags = compute_system_tags(
                f,
                duplicate=str(f.path) in dup_paths,
                large_threshold=large_threshold,
                recent_days=recent_days,
            )
            for tag in tags:
                tag_id = _ensure_tag(conn, tag, "system")
                conn.execute(
                    "INSERT OR IGNORE INTO file_tags "
                    "(file_id, tag_id, confidence, source) "
                    "VALUES (?, ?, ?, 'system')",
                    (row["id"], tag_id, 1.0),
                )
                written += 1
    return written


# ---- 内容关键词标签（识别内容自动打标签，无需训练数据） ----

def assign_content_tags(
    db: Database,
    files: Iterable[ScannedFile],
    *,
    texts: dict[str, str | None] | None = None,
    top_n: int = 2,
) -> int:
    """基于内容关键词自动打标签：每文件取 top_n 个关键词写入 learned 标签。

    - ``texts`` 为 {path: 提取文本} 复用一次提取（不传则内部重新 extract_text）；
    - 关键词与系统标签词汇冲突时跳过（避免 tags.kind 首写获胜变只读）；
    - 置信度 = 归一化频次，夹在 [0.4, 0.9]；
    - 用户接受/拒绝这些标签会自动写入 training_feedback，成为 ML 训练数据。
    返回写入的 file_tags 关联条数。
    """
    files = list(files)
    written = 0
    with db.transaction() as conn:
        for f in files:
            row = conn.execute(
                "SELECT id FROM files WHERE path = ?", (str(f.path),)
            ).fetchone()
            if row is None:
                continue  # 未索引，跳过
            if texts is not None:
                text = texts.get(str(f.path))
            else:
                text = extract_text(f.path)
            if not text:
                continue
            for tag, score in keyword_scores(text, top_n=top_n):
                if tag in SYSTEM_TAG_NAMES:
                    continue
                tag_id = _ensure_tag(conn, tag, "learned")
                confidence = round(min(0.9, max(0.4, score)), 3)
                conn.execute(
                    "INSERT OR IGNORE INTO file_tags "
                    "(file_id, tag_id, confidence, source) "
                    "VALUES (?, ?, ?, 'learned')",
                    (row["id"], tag_id, confidence),
                )
                written += 1
    return written


# ---- Phase 3：学习标签 ----

# 训练所需的最少已标注样本数 / 标签种类数
LEARNED_MIN_SAMPLES = 3
# 置信度阈值：低于该值的预测标签不写入
LEARNED_THRESHOLD = 0.35
# 每个文件最多写入的学习标签数
LEARNED_TOP_K = 3


def assign_learned_tags(
    db: Database,
    files: Iterable[ScannedFile],
    *,
    min_samples: int = LEARNED_MIN_SAMPLES,
    threshold: float = LEARNED_THRESHOLD,
    top_k: int = LEARNED_TOP_K,
    texts: dict[str, str | None] | None = None,
) -> int:
    """基于用户修正样本训练分类器，为已索引文件预测 learned 标签并写库。

    流程：提取文本 → TF-IDF（全量语料上估计 IDF）→ 用已标注文件训练
    OneVsRest 分类器 → 对全部文件预测 → 按置信度写 ``file_tags``
    （source='learned'）。

    训练数据不足（已标注文件少于 ``min_samples``，或标签种类少于 2 个）
    时返回 0，不做预测。返回写入的 file_tags 关联条数。
    """
    files = list(files)
    if not files:
        return 0

    labels_by_path = {str(f.path): tags for f, tags in load_training_data(db)}
    labeled = [f for f in files if str(f.path) in labels_by_path]
    if len(labeled) < min_samples:
        return 0
    all_tags = set().union(*labels_by_path.values()) if labels_by_path else set()
    if len(all_tags) < 2:
        return 0

    # 全量语料统一提取文本并拟合适配 IDF，避免对同一文件重复解析
    corpus = build_corpus(files, texts=texts)
    vectorizer = make_vectorizer()
    try:
        X = vectorizer.fit_transform(corpus)
    except ValueError:
        return 0  # 语料无法产生任何特征（如全部是单字符文件名），跳过
    idx = {str(f.path): i for i, f in enumerate(files)}
    X_train = X[[idx[str(f.path)] for f in labeled]]
    y_train = [labels_by_path[str(f.path)] for f in labeled]

    classifier = TagClassifier(threshold=threshold, top_k=top_k)
    classifier.train(X_train, y_train)
    predictions = classifier.predict(X)

    written = 0
    with db.transaction() as conn:
        for f, tags in zip(files, predictions):
            row = conn.execute(
                "SELECT id FROM files WHERE path = ?", (str(f.path),)
            ).fetchone()
            if row is None:
                continue  # 未索引，跳过
            for tag, score in tags:
                tag_id = _ensure_tag(conn, tag, "learned")
                conn.execute(
                    "INSERT OR IGNORE INTO file_tags "
                    "(file_id, tag_id, confidence, source) "
                    "VALUES (?, ?, ?, 'learned')",
                    (row["id"], tag_id, score),
                )
                written += 1
    return written
