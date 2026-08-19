# =============================================================================
# tests/test_scanner.py —— 文件扫描器
# =============================================================================

from app.core.scanner import Scanner


def test_scan_excludes_db_and_sidecars(tmp_path):
    """扫描时应跳过数据库本体及其 WAL/SHM 伴生文件。"""
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    db_path = tmp_path / "index.db"
    # 模拟 WAL 模式伴生文件已存在
    (tmp_path / "index.db-wal").write_bytes(b"\x00")
    (tmp_path / "index.db-shm").write_bytes(b"\x00")

    files = Scanner.scan(tmp_path, db_path=db_path)
    names = {f.name for f in files}
    assert names == {"a.txt", "b.txt"}
    assert "index.db" not in names
    assert "index.db-wal" not in names
    assert "index.db-shm" not in names


def test_scan_ignores_hidden_by_default(tmp_path):
    (tmp_path / ".hidden.txt").write_text("h", encoding="utf-8")
    (tmp_path / "visible.txt").write_text("v", encoding="utf-8")
    names = {f.name for f in Scanner.scan(tmp_path)}
    assert names == {"visible.txt"}


def test_scan_recurses_into_subdirectories(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "inner.txt").write_text("x", encoding="utf-8")
    (tmp_path / "root.txt").write_text("y", encoding="utf-8")
    names = {f.name for f in Scanner.scan(tmp_path)}
    assert names == {"inner.txt", "root.txt"}


def test_scan_skips_files_whose_stat_fails(tmp_path):
    (tmp_path / "ok.txt").write_text("ok", encoding="utf-8")
    # 悬空符号链接：stat 跟随目标时抛 OSError，应被静默跳过
    (tmp_path / "broken.txt").symlink_to(tmp_path / "missing-target")
    names = {f.name for f in Scanner.scan(tmp_path)}
    assert names == {"ok.txt"}
