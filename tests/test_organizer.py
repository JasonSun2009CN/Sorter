# =============================================================================
# tests/test_organizer.py —— 组织引擎（Phase 5 纯逻辑）
# =============================================================================

from pathlib import Path

from app.core.organizer import (
    KIND_EXTENSION,
    KIND_TAG,
    KIND_TYPE,
    KIND_YEAR_CREATED,
    KIND_YEAR_MODIFIED,
    MovePlan,
    Rule,
    RuleLevel,
    apply_level,
    build_plan,
    compute_target,
    describe_level,
    rule_from_dict,
    rule_to_dict,
    _same_location,
    _sanitize_segment,
)
from app.core.scanner import ScannedFile


def _file(name="a.pdf", ctime=1_700_000_000.0, mtime=1_800_000_000.0, root="."):
    return ScannedFile(path=Path(root) / name, size=1, mtime=mtime, ctime=ctime)


# ---- apply_level ----

def test_apply_level_tag_present():
    f = _file()
    assert apply_level(f, {"School"}, RuleLevel(KIND_TAG, "School")) == "School"


def test_apply_level_tag_missing_returns_none():
    f = _file()
    assert apply_level(f, {"Math"}, RuleLevel(KIND_TAG, "School")) is None


def test_apply_level_tag_sanitizes():
    f = _file()
    assert apply_level(f, {"a/b:c"}, RuleLevel(KIND_TAG, "a/b:c")) == "a_b_c"


def test_apply_level_type():
    assert apply_level(_file("doc.pdf"), set(), RuleLevel(KIND_TYPE)) == "PDF"
    assert apply_level(_file("pic.png"), set(), RuleLevel(KIND_TYPE)) == "IMAGE"


def test_apply_level_type_unknown_falls_back_to_extension():
    f = _file("blob.xyz")
    assert apply_level(f, set(), RuleLevel(KIND_TYPE)) == "XYZ"
    f2 = _file("noext")
    assert apply_level(f2, set(), RuleLevel(KIND_TYPE)) == "其他"


def test_apply_level_extension():
    assert apply_level(_file("a.txt"), set(), RuleLevel(KIND_EXTENSION)) == "TXT"
    assert apply_level(_file("noext"), set(), RuleLevel(KIND_EXTENSION)) == "其他"


def test_apply_level_year():
    assert apply_level(_file(ctime=0), set(), RuleLevel(KIND_YEAR_CREATED)) == "未知"
    assert apply_level(_file(mtime=0), set(), RuleLevel(KIND_YEAR_MODIFIED)) == "未知"
    # 1_700_000_000 ≈ 2023-11-14
    assert apply_level(_file(ctime=1_700_000_000), set(), RuleLevel(KIND_YEAR_CREATED)) == "2023"


# ---- _sanitize_segment ----

def test_sanitize_segment_vectors():
    cases = {
        " School ": "School",
        "a/b:c": "a_b_c",
        "..": "_",
        ".hidden": "_hidden",
        "": "其他",
        "name.": "name",
        "中文 标签": "中文 标签",
        "a\tb\nc": "a_b_c",
    }
    for raw, expected in cases.items():
        assert _sanitize_segment(raw) == expected, f"{raw!r} -> {expected!r}"


def test_sanitize_never_contains_separator():
    for raw in ["a/b", "a\\b", "a:b", "../x", "..", ".", " "] * 3:
        out = _sanitize_segment(raw)
        assert "/" not in out and "\\" not in out and out != ".."


# ---- compute_target ----

def test_compute_target_nested():
    f = _file()
    rule = Rule([RuleLevel(KIND_TAG, "School"), RuleLevel(KIND_TYPE)])
    assert compute_target(f, {"School"}, rule) == Path("School/PDF")


def test_compute_target_missing_tag_returns_none():
    f = _file()
    rule = Rule([RuleLevel(KIND_TAG, "School"), RuleLevel(KIND_TYPE)])
    assert compute_target(f, {"Math"}, rule) is None


def test_compute_target_empty_rule_returns_none():
    assert compute_target(_file(), set(), Rule()) is None


# ---- build_plan ----

def _in(tmp_path, name):
    return ScannedFile.from_path(tmp_path / name)


def test_build_plan_basic(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    files = [_in(tmp_path, "a.pdf")]
    rule = Rule([RuleLevel(KIND_TYPE)])
    plans = build_plan([(files[0], set())], rule, tmp_path)
    assert len(plans) == 1
    assert plans[0].source == tmp_path / "a.pdf"
    assert plans[0].target == tmp_path / "PDF" / "a.pdf"
    assert plans[0].reason == "PDF"


def test_build_plan_skips_unmatched_and_already_placed(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    (tmp_path / "PDF").mkdir()
    (tmp_path / "PDF" / "a.pdf").write_bytes(b"%PDF")  # 已就位
    f = _in(tmp_path, "a.pdf")
    rule = Rule([RuleLevel(KIND_TAG, "School"), RuleLevel(KIND_TYPE)])
    # 缺 tag → 不适用；即便就位检查也不该产生计划
    assert build_plan([(f, set())], rule, tmp_path) == []


def test_build_plan_skips_already_placed_matching(tmp_path):
    # 文件已位于目标位置（PDF/a.pdf）→ target == source → 跳过
    (tmp_path / "PDF").mkdir()
    (tmp_path / "PDF" / "a.pdf").write_bytes(b"%PDF")
    f = _in(tmp_path, "PDF/a.pdf")
    rule = Rule([RuleLevel(KIND_TYPE)])
    assert build_plan([(f, set())], rule, tmp_path) == []


def test_build_plan_empty_rule_returns_empty(tmp_path):
    assert build_plan([], Rule(), tmp_path) == []


def test_build_plan_targets_are_moveplan(tmp_path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    f = _in(tmp_path, "a.txt")
    plans = build_plan([(f, set())], Rule([RuleLevel(KIND_EXTENSION)]), tmp_path)
    assert isinstance(plans[0], MovePlan)


def test_same_location_casefold_on_darwin():
    assert _same_location(Path("/tmp/Foo/x"), Path("/tmp/foo/x"))


# ---- 序列化 ----

def test_rule_roundtrip():
    rule = Rule([
        RuleLevel(KIND_TAG, "School"),
        RuleLevel(KIND_TYPE),
        RuleLevel(KIND_YEAR_CREATED),
    ])
    restored = rule_from_dict(rule_to_dict(rule))
    assert restored.levels == rule.levels


def test_rule_from_dict_ignores_unknown_kind():
    rule = rule_from_dict({"levels": [{"kind": "bogus", "value": "x"}, {"kind": KIND_TYPE, "value": ""}]})
    assert len(rule.levels) == 1
    assert rule.levels[0].kind == KIND_TYPE


# ---- describe_level ----

def test_describe_level():
    assert describe_level(RuleLevel(KIND_TAG, "School")) == "按标签：School"
    assert describe_level(RuleLevel(KIND_TYPE)) == "按文件类型"
    assert describe_level(RuleLevel(KIND_EXTENSION)) == "按扩展名"
    assert describe_level(RuleLevel(KIND_YEAR_CREATED)) == "按创建年份"
    assert describe_level(RuleLevel(KIND_YEAR_MODIFIED)) == "按修改年份"


# ---- Phase 7：安全移动 ----

def test_move_file_creates_target_dir_and_moves(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("x", encoding="utf-8")
    from app.core.organizer import move_file
    move_file(src, tmp_path / "Nested" / "dir" / "a.txt")
    assert not src.exists()
    assert (tmp_path / "Nested" / "dir" / "a.txt").read_text(encoding="utf-8") == "x"


def test_move_file_refuses_overwrite(tmp_path):
    from app.core.organizer import move_file
    src = tmp_path / "a.txt"
    src.write_text("x", encoding="utf-8")
    (tmp_path / "b.txt").write_text("y", encoding="utf-8")
    try:
        move_file(src, tmp_path / "b.txt")
    except FileExistsError:
        pass
    else:
        assert False, "应拒绝覆盖已有目标"
    assert src.exists() and (tmp_path / "b.txt").read_text(encoding="utf-8") == "y"


def test_apply_plan_moves_and_returns_pairs(tmp_path):
    from app.core.organizer import MovePlan, apply_plan
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "b.txt").write_text("y", encoding="utf-8")
    plans = [
        MovePlan(source=tmp_path / "a.txt", target=tmp_path / "TXT" / "a.txt", reason="TXT"),
        MovePlan(source=tmp_path / "b.txt", target=tmp_path / "TXT" / "b.txt", reason="TXT"),
    ]
    moved, errors = apply_plan(plans)
    assert errors == []
    assert moved == [(tmp_path / "a.txt", tmp_path / "TXT" / "a.txt"),
                     (tmp_path / "b.txt", tmp_path / "TXT" / "b.txt")]


def test_apply_plan_refuses_overwrite_continues(tmp_path):
    from app.core.organizer import MovePlan, apply_plan
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "b.txt").write_text("y", encoding="utf-8")
    (tmp_path / "TXT").mkdir()
    (tmp_path / "TXT" / "b.txt").write_text("occupied", encoding="utf-8")  # 预占用 b 的目标
    plans = [
        MovePlan(source=tmp_path / "a.txt", target=tmp_path / "TXT" / "a.txt", reason="TXT"),
        MovePlan(source=tmp_path / "b.txt", target=tmp_path / "TXT" / "b.txt", reason="TXT"),
    ]
    moved, errors = apply_plan(plans)
    assert len(moved) == 1 and moved[0][1].name == "a.txt"
    assert len(errors) == 1 and "拒绝覆盖" in errors[0]
    assert (tmp_path / "b.txt").exists()  # b 未被覆盖、仍在原处


def test_apply_plan_source_missing(tmp_path):
    from app.core.organizer import MovePlan, apply_plan
    plans = [MovePlan(source=tmp_path / "nope.txt", target=tmp_path / "TXT" / "nope.txt", reason="TXT")]
    moved, errors = apply_plan(plans)
    assert moved == []
    assert len(errors) == 1


def test_apply_plan_target_parent_is_file(tmp_path):
    from app.core.organizer import MovePlan, apply_plan
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "TXT").write_text("I am a file", encoding="utf-8")  # 目标父目录是文件
    plans = [MovePlan(source=tmp_path / "a.txt", target=tmp_path / "TXT" / "a.txt", reason="TXT")]
    moved, errors = apply_plan(plans)
    assert moved == []
    assert len(errors) == 1


def test_apply_plan_skips_same_location(tmp_path):
    from app.core.organizer import MovePlan, apply_plan
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    plans = [MovePlan(source=tmp_path / "a.txt", target=tmp_path / "a.txt", reason="TXT")]
    moved, errors = apply_plan(plans)
    assert moved == []
    assert errors == []
