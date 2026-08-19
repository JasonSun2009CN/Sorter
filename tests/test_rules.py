# =============================================================================
# tests/test_rules.py —— 组织规则持久化（Phase 5）
# =============================================================================

from app.core.organizer import KIND_EXTENSION, KIND_TAG, KIND_TYPE, Rule, RuleLevel
from app.database import Database
from app.database.rules import (
    delete_rule,
    get_last_rule,
    get_rule,
    load_rules,
    save_rule,
)


def _db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def _rule(*levels):
    return Rule(list(levels))


def test_save_and_get_rule(tmp_path):
    db = _db(tmp_path)
    rule = _rule(RuleLevel(KIND_TAG, "School"), RuleLevel(KIND_TYPE))
    rid = save_rule(db, "我的规则", rule)
    assert rid > 0
    result = get_rule(db, rid)
    assert result is not None
    name, restored = result
    assert name == "我的规则"
    assert restored.levels == rule.levels


def test_save_same_name_upserts(tmp_path):
    db = _db(tmp_path)
    r1 = save_rule(db, "默认规则", _rule(RuleLevel(KIND_TYPE)))
    r2 = save_rule(db, "默认规则", _rule(RuleLevel(KIND_EXTENSION)))
    assert r1 == r2  # 同一行，更新
    rows = db.query("SELECT COUNT(*) AS n FROM rules")
    assert rows[0]["n"] == 1
    result = get_rule(db, r1)
    assert result is not None
    rule = result[1]
    assert rule.levels[0].kind == KIND_EXTENSION


def test_load_rules_ordered_by_updated(tmp_path):
    db = _db(tmp_path)
    save_rule(db, "旧规则", _rule(RuleLevel(KIND_TYPE)))
    save_rule(db, "新规则", _rule(RuleLevel(KIND_EXTENSION)))
    rules = load_rules(db)
    assert len(rules) == 2
    assert rules[0][1] == "新规则"  # 最近更新的在前


def test_get_last_rule(tmp_path):
    db = _db(tmp_path)
    save_rule(db, "旧", _rule(RuleLevel(KIND_TYPE)))
    save_rule(db, "新", _rule(RuleLevel(KIND_EXTENSION)))
    result = get_last_rule(db)
    assert result is not None
    name, rule = result
    assert name == "新"
    assert rule.levels[0].kind == KIND_EXTENSION


def test_get_last_rule_empty_db(tmp_path):
    assert get_last_rule(_db(tmp_path)) is None


def test_delete_rule(tmp_path):
    db = _db(tmp_path)
    rid = save_rule(db, "默认规则", _rule(RuleLevel(KIND_TYPE)))
    delete_rule(db, rid)
    assert get_rule(db, rid) is None
    assert get_last_rule(db) is None
