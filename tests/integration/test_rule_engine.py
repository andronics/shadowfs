#!/usr/bin/env python3
"""Comprehensive tests for RuleEngine."""

import os
import tempfile
import time

import pytest

from shadowfs.integration.pattern_matcher import PatternType
from shadowfs.integration.rule_engine import (
    Condition,
    Rule,
    RuleAction,
    RuleEngine,
    RuleOperator,
    get_file_attrs,
)


class TestRuleAction:
    """Tests for RuleAction enum."""

    def test_include(self):
        """Test INCLUDE action."""
        assert RuleAction.INCLUDE.value == "include"

    def test_exclude(self):
        """Test EXCLUDE action."""
        assert RuleAction.EXCLUDE.value == "exclude"


class TestRuleOperator:
    """Tests for RuleOperator enum."""

    def test_and(self):
        """Test AND operator."""
        assert RuleOperator.AND.value == "and"

    def test_or(self):
        """Test OR operator."""
        assert RuleOperator.OR.value == "or"

    def test_not(self):
        """Test NOT operator."""
        assert RuleOperator.NOT.value == "not"


class TestCondition:
    """Tests for Condition dataclass."""

    def test_creation(self):
        """Test creating Condition."""
        cond = Condition(field="size", operator="gt", value=1024)

        assert cond.field == "size"
        assert cond.operator == "gt"
        assert cond.value == 1024


class TestRule:
    """Tests for Rule dataclass."""

    def test_creation_minimal(self):
        """Test creating minimal Rule."""
        rule = Rule(action=RuleAction.EXCLUDE)

        assert rule.action == RuleAction.EXCLUDE
        assert rule.name is None
        assert rule.patterns == []
        assert rule.conditions == []
        assert rule.priority == 0
        assert rule.enabled is True

    def test_creation_full(self):
        """Test creating full Rule."""
        conditions = [Condition(field="size", operator="gt", value=1024)]

        rule = Rule(
            action=RuleAction.INCLUDE,
            name="large_files",
            patterns=["*.bin"],
            pattern_type=PatternType.GLOB,
            conditions=conditions,
            condition_operator=RuleOperator.AND,
            priority=10,
            enabled=True,
        )

        assert rule.action == RuleAction.INCLUDE
        assert rule.name == "large_files"
        assert rule.patterns == ["*.bin"]
        assert rule.pattern_type == PatternType.GLOB
        assert rule.conditions == conditions
        assert rule.condition_operator == RuleOperator.AND
        assert rule.priority == 10
        assert rule.enabled is True


class TestRuleEngine:
    """Tests for RuleEngine class."""

    def test_init_default(self):
        """Test default initialization."""
        engine = RuleEngine()

        assert engine.get_default_action() == RuleAction.INCLUDE
        assert len(engine) == 0

    def test_init_custom_default(self):
        """Test initialization with custom default action."""
        engine = RuleEngine(default_action=RuleAction.EXCLUDE)

        assert engine.get_default_action() == RuleAction.EXCLUDE

    def test_add_rule(self):
        """Test adding rule."""
        engine = RuleEngine()
        rule = Rule(action=RuleAction.EXCLUDE, patterns=["*.pyc"])

        engine.add_rule(rule)

        assert len(engine) == 1
        rules = engine.get_rules()
        assert len(rules) == 1
        assert rules[0] == rule

    def test_add_multiple_rules_priority_sorting(self):
        """Test that rules are sorted by priority."""
        engine = RuleEngine()

        rule1 = Rule(action=RuleAction.EXCLUDE, priority=1, name="low")
        rule2 = Rule(action=RuleAction.INCLUDE, priority=10, name="high")
        rule3 = Rule(action=RuleAction.EXCLUDE, priority=5, name="mid")

        engine.add_rule(rule1)
        engine.add_rule(rule2)
        engine.add_rule(rule3)

        rules = engine.get_rules()
        assert rules[0].name == "high"  # priority 10
        assert rules[1].name == "mid"  # priority 5
        assert rules[2].name == "low"  # priority 1

    def test_remove_rule(self):
        """Test removing rule by name."""
        engine = RuleEngine()

        rule1 = Rule(action=RuleAction.EXCLUDE, name="rule1", patterns=["*.pyc"])
        rule2 = Rule(action=RuleAction.INCLUDE, name="rule2", patterns=["*.py"])

        engine.add_rule(rule1)
        engine.add_rule(rule2)

        assert len(engine) == 2

        removed = engine.remove_rule("rule1")
        assert removed is True
        assert len(engine) == 1

        rules = engine.get_rules()
        assert rules[0].name == "rule2"

    def test_remove_rule_not_found(self):
        """Test removing non-existent rule."""
        engine = RuleEngine()
        rule = Rule(action=RuleAction.EXCLUDE, name="rule1")
        engine.add_rule(rule)

        removed = engine.remove_rule("nonexistent")
        assert removed is False
        assert len(engine) == 1

    def test_clear_rules(self):
        """Test clearing all rules."""
        engine = RuleEngine()

        engine.add_rule(Rule(action=RuleAction.EXCLUDE, patterns=["*.pyc"]))
        engine.add_rule(Rule(action=RuleAction.INCLUDE, patterns=["*.py"]))

        assert len(engine) == 2

        engine.clear_rules()
        assert len(engine) == 0

    def test_should_show_default_include(self):
        """Test default action is INCLUDE when no rules match."""
        engine = RuleEngine()

        assert engine.should_show("test.py") is True
        assert engine.should_show("anything") is True

    def test_should_show_default_exclude(self):
        """Test default action is EXCLUDE when no rules match."""
        engine = RuleEngine(default_action=RuleAction.EXCLUDE)

        assert engine.should_show("test.py") is False
        assert engine.should_show("anything") is False

    def test_should_show_exclude_rule(self):
        """Test exclude rule hides files."""
        engine = RuleEngine()
        engine.add_rule(Rule(action=RuleAction.EXCLUDE, patterns=["*.pyc"]))

        assert engine.should_show("test.py") is True
        assert engine.should_show("test.pyc") is False

    def test_should_show_include_rule(self):
        """Test include rule shows files."""
        engine = RuleEngine(default_action=RuleAction.EXCLUDE)
        engine.add_rule(Rule(action=RuleAction.INCLUDE, patterns=["*.py"]))

        assert engine.should_show("test.py") is True
        assert engine.should_show("test.txt") is False

    def test_should_show_first_match_wins(self):
        """Test first-match-wins precedence."""
        engine = RuleEngine()

        # Higher priority rule excludes test files
        engine.add_rule(
            Rule(action=RuleAction.EXCLUDE, patterns=["test_*.py"], priority=10)
        )

        # Lower priority rule includes all Python files
        engine.add_rule(
            Rule(action=RuleAction.INCLUDE, patterns=["*.py"], priority=1)
        )

        assert engine.should_show("main.py") is True  # Matches lower priority rule
        assert engine.should_show("test_main.py") is False  # Matches higher priority rule

    def test_should_show_disabled_rule(self):
        """Test disabled rule is not evaluated."""
        engine = RuleEngine()
        rule = Rule(action=RuleAction.EXCLUDE, patterns=["*.pyc"], enabled=False)
        engine.add_rule(rule)

        # Rule is disabled, should use default action
        assert engine.should_show("test.pyc") is True

    def test_enable_disable_rule(self):
        """Test enabling and disabling rules."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE, name="exclude_pyc", patterns=["*.pyc"]
        )
        engine.add_rule(rule)

        # Initially enabled
        assert engine.should_show("test.pyc") is False

        # Disable rule
        disabled = engine.disable_rule("exclude_pyc")
        assert disabled is True
        assert engine.should_show("test.pyc") is True

        # Re-enable rule
        enabled = engine.enable_rule("exclude_pyc")
        assert enabled is True
        assert engine.should_show("test.pyc") is False

    def test_enable_rule_not_found(self):
        """Test enabling non-existent rule."""
        engine = RuleEngine()
        result = engine.enable_rule("nonexistent")
        assert result is False

    def test_disable_rule_not_found(self):
        """Test disabling non-existent rule."""
        engine = RuleEngine()
        result = engine.disable_rule("nonexistent")
        assert result is False

    def test_condition_eq(self):
        """Test equality condition."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[Condition(field="size", operator="eq", value=1024)],
        )
        engine.add_rule(rule)

        attrs_match = {"size": 1024}
        attrs_no_match = {"size": 2048}

        assert engine.should_show("test.txt", attrs_match) is False
        assert engine.should_show("test.txt", attrs_no_match) is True

    def test_condition_ne(self):
        """Test not-equal condition."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[Condition(field="size", operator="ne", value=0)],
        )
        engine.add_rule(rule)

        assert engine.should_show("test.txt", {"size": 1024}) is False
        assert engine.should_show("test.txt", {"size": 0}) is True

    def test_condition_lt(self):
        """Test less-than condition."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[Condition(field="size", operator="lt", value=1024)],
        )
        engine.add_rule(rule)

        assert engine.should_show("test.txt", {"size": 512}) is False
        assert engine.should_show("test.txt", {"size": 2048}) is True

    def test_condition_le(self):
        """Test less-than-or-equal condition."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[Condition(field="size", operator="le", value=1024)],
        )
        engine.add_rule(rule)

        assert engine.should_show("test.txt", {"size": 1024}) is False
        assert engine.should_show("test.txt", {"size": 512}) is False
        assert engine.should_show("test.txt", {"size": 2048}) is True

    def test_condition_gt(self):
        """Test greater-than condition."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[Condition(field="size", operator="gt", value=1024)],
        )
        engine.add_rule(rule)

        assert engine.should_show("test.txt", {"size": 2048}) is False
        assert engine.should_show("test.txt", {"size": 512}) is True

    def test_condition_ge(self):
        """Test greater-than-or-equal condition."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[Condition(field="size", operator="ge", value=1024)],
        )
        engine.add_rule(rule)

        assert engine.should_show("test.txt", {"size": 1024}) is False
        assert engine.should_show("test.txt", {"size": 2048}) is False
        assert engine.should_show("test.txt", {"size": 512}) is True

    def test_condition_contains(self):
        """Test contains condition."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[Condition(field="permissions", operator="contains", value="r")],
        )
        engine.add_rule(rule)

        assert engine.should_show("test.txt", {"permissions": "rw-r--r--"}) is False
        assert engine.should_show("test.txt", {"permissions": "-w-------"}) is True

    def test_condition_startswith(self):
        """Test startswith condition."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[Condition(field="permissions", operator="startswith", value="-rw")],
        )
        engine.add_rule(rule)

        assert engine.should_show("test.txt", {"permissions": "-rw-r--r--"}) is False
        assert engine.should_show("test.txt", {"permissions": "drwxr-xr-x"}) is True

    def test_condition_endswith(self):
        """Test endswith condition."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[Condition(field="permissions", operator="endswith", value="r--")],
        )
        engine.add_rule(rule)

        assert engine.should_show("test.txt", {"permissions": "-rw-r--r--"}) is False
        assert engine.should_show("test.txt", {"permissions": "-rw-rw-rw-"}) is True

    def test_condition_matches_regex(self):
        """Test regex matches condition."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[Condition(field="name", operator="matches", value=r"test_\d+")],
        )
        engine.add_rule(rule)

        assert engine.should_show("file", {"name": "test_123"}) is False
        assert engine.should_show("file", {"name": "test_abc"}) is True

    def test_condition_and_operator(self):
        """Test AND operator for conditions."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[
                Condition(field="size", operator="gt", value=1024),
                Condition(field="is_file", operator="eq", value=True),
            ],
            condition_operator=RuleOperator.AND,
        )
        engine.add_rule(rule)

        # Both conditions match
        assert engine.should_show("test.txt", {"size": 2048, "is_file": True}) is False

        # Only one condition matches
        assert engine.should_show("test.txt", {"size": 2048, "is_file": False}) is True
        assert engine.should_show("test.txt", {"size": 512, "is_file": True}) is True

    def test_condition_or_operator(self):
        """Test OR operator for conditions."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[
                Condition(field="size", operator="gt", value=1024),
                Condition(field="is_dir", operator="eq", value=True),
            ],
            condition_operator=RuleOperator.OR,
        )
        engine.add_rule(rule)

        # Either condition matches
        assert engine.should_show("test.txt", {"size": 2048, "is_dir": False}) is False
        assert engine.should_show("test.txt", {"size": 512, "is_dir": True}) is False

        # Neither condition matches
        assert engine.should_show("test.txt", {"size": 512, "is_dir": False}) is True

    def test_condition_not_operator(self):
        """Test NOT operator for conditions."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[Condition(field="size", operator="eq", value=0)],
            condition_operator=RuleOperator.NOT,
        )
        engine.add_rule(rule)

        # Condition matches, but NOT inverts it
        assert engine.should_show("test.txt", {"size": 0}) is True

        # Condition doesn't match, NOT inverts it
        assert engine.should_show("test.txt", {"size": 1024}) is False

    def test_condition_missing_field(self):
        """Test condition with missing field."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[Condition(field="nonexistent", operator="eq", value=123)],
        )
        engine.add_rule(rule)

        # Missing field means condition doesn't match
        assert engine.should_show("test.txt", {"size": 1024}) is True

    def test_condition_no_attrs(self):
        """Test conditions when no attrs provided."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=["*"],
            conditions=[Condition(field="size", operator="gt", value=1024)],
        )
        engine.add_rule(rule)

        # No attrs means condition cannot be evaluated, rule doesn't match
        assert engine.should_show("test.txt") is True

    def test_get_matching_rules(self):
        """Test getting all matching rules."""
        engine = RuleEngine()

        rule1 = Rule(action=RuleAction.EXCLUDE, name="rule1", patterns=["*.py"])
        rule2 = Rule(action=RuleAction.INCLUDE, name="rule2", patterns=["test_*.py"])

        engine.add_rule(rule1)
        engine.add_rule(rule2)

        # Matches both rules
        matches = engine.get_matching_rules("test_foo.py")
        assert len(matches) == 2
        assert any(r.name == "rule1" for r in matches)
        assert any(r.name == "rule2" for r in matches)

        # Matches only rule1
        matches = engine.get_matching_rules("main.py")
        assert len(matches) == 1
        assert matches[0].name == "rule1"

    def test_set_default_action(self):
        """Test setting default action."""
        engine = RuleEngine()

        assert engine.get_default_action() == RuleAction.INCLUDE

        engine.set_default_action(RuleAction.EXCLUDE)
        assert engine.get_default_action() == RuleAction.EXCLUDE

    def test_regex_pattern_type(self):
        """Test using regex patterns."""
        engine = RuleEngine()
        rule = Rule(
            action=RuleAction.EXCLUDE,
            patterns=[r"test_\d+\.py$"],
            pattern_type=PatternType.REGEX,
        )
        engine.add_rule(rule)

        assert engine.should_show("test_123.py") is False
        assert engine.should_show("test_abc.py") is True


class TestGetFileAttrs:
    """Tests for get_file_attrs helper function."""

    def test_get_file_attrs(self):
        """Test getting file attributes."""
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            attrs = get_file_attrs(temp_path)

            # Check all expected attributes
            assert "size" in attrs
            assert "mtime" in attrs
            assert "ctime" in attrs
            assert "atime" in attrs
            assert "mode" in attrs
            assert "uid" in attrs
            assert "gid" in attrs
            assert "is_file" in attrs
            assert "is_dir" in attrs
            assert "is_symlink" in attrs
            assert "permissions" in attrs

            # Verify values
            assert attrs["size"] > 0
            assert attrs["is_file"] is True
            assert attrs["is_dir"] is False
            assert attrs["is_symlink"] is False

        finally:
            os.unlink(temp_path)

    def test_get_file_attrs_nonexistent(self):
        """Test getting attrs for nonexistent file."""
        attrs = get_file_attrs("/nonexistent/file/path")
        assert attrs == {}
