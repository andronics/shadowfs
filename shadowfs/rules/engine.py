#!/usr/bin/env python3
"""Rule engine for file visibility evaluation.

This module provides rule-based filtering for ShadowFS:
- Include/exclude rules with precedence
- Attribute-based conditions (size, date, permissions)
- Pattern matching integration
- Logical operators (AND, OR, NOT)
- First-match-wins evaluation

Example:
    >>> engine = RuleEngine()
    >>> engine.add_rule(Rule(
    ...     action=RuleAction.EXCLUDE,
    ...     patterns=["*.pyc", "__pycache__/**"],
    ... ))
    >>> engine.should_show("test.pyc", file_attrs)
    False
"""

import os
import stat
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

from shadowfs.rules.patterns import PatternMatcher, PatternType


class RuleAction(Enum):
    """Action to take when rule matches."""

    INCLUDE = "include"  # Show file
    EXCLUDE = "exclude"  # Hide file


class RuleOperator(Enum):
    """Logical operator for combining conditions."""

    AND = "and"  # All conditions must match
    OR = "or"  # Any condition must match
    NOT = "not"  # Negate the condition


@dataclass
class Condition:
    """A single condition for rule evaluation."""

    field: str  # Attribute name (size, mtime, mode, etc.)
    operator: str  # Comparison operator (eq, ne, lt, le, gt, ge, contains)
    value: Any  # Value to compare against


@dataclass
class Rule:
    """A rule for file visibility evaluation.

    Rules are evaluated in order. First matching rule determines visibility.
    """

    action: RuleAction
    name: Optional[str] = None
    patterns: List[str] = field(default_factory=list)
    pattern_type: PatternType = PatternType.GLOB
    conditions: List[Condition] = field(default_factory=list)
    condition_operator: RuleOperator = RuleOperator.AND
    priority: int = 0  # Higher priority evaluated first
    enabled: bool = True


class RuleEngine:
    """Rule engine for evaluating file visibility.

    Features:
    - First-match-wins precedence
    - Pattern-based matching
    - Attribute conditions
    - Priority-based ordering
    - Default behavior (include or exclude)
    """

    def __init__(self, default_action: RuleAction = RuleAction.INCLUDE):
        """Initialize rule engine.

        Args:
            default_action: Action to take when no rules match
        """
        self._rules: List[Rule] = []
        self._default_action = default_action
        self._pattern_matchers: Dict[str, PatternMatcher] = {}

    def add_rule(self, rule: Rule) -> None:
        """Add rule to engine.

        Args:
            rule: Rule to add
        """
        self._rules.append(rule)

        # Sort by priority (higher first)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

        # Build pattern matcher for this rule
        if rule.patterns:
            matcher = PatternMatcher()
            for pattern in rule.patterns:
                if rule.pattern_type == PatternType.GLOB:
                    matcher.add_glob_pattern(pattern)
                else:
                    matcher.add_regex_pattern(pattern)

            rule_id = id(rule)
            self._pattern_matchers[str(rule_id)] = matcher

    def remove_rule(self, name: str) -> bool:
        """Remove rule by name.

        Args:
            name: Name of rule to remove

        Returns:
            True if rule was found and removed
        """
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                rule_id = str(id(rule))
                if rule_id in self._pattern_matchers:
                    del self._pattern_matchers[rule_id]
                self._rules.pop(i)
                return True
        return False

    def clear_rules(self) -> None:
        """Clear all rules."""
        self._rules.clear()
        self._pattern_matchers.clear()

    def should_show(self, path: str, file_attrs: Optional[Dict[str, Any]] = None) -> bool:
        """Determine if file should be visible.

        Args:
            path: File path to evaluate
            file_attrs: Optional file attributes (stat result, metadata)

        Returns:
            True if file should be shown
        """
        # Evaluate rules in order
        for rule in self._rules:
            if not rule.enabled:
                continue

            if self._evaluate_rule(rule, path, file_attrs):
                # Rule matched, apply action
                return rule.action == RuleAction.INCLUDE

        # No rules matched, use default action
        return self._default_action == RuleAction.INCLUDE

    def _evaluate_rule(self, rule: Rule, path: str, file_attrs: Optional[Dict[str, Any]]) -> bool:
        """Evaluate if rule matches path.

        Args:
            rule: Rule to evaluate
            path: File path
            file_attrs: File attributes

        Returns:
            True if rule matches
        """
        # Check pattern matching
        if rule.patterns:
            rule_id = str(id(rule))
            matcher = self._pattern_matchers.get(rule_id)
            if matcher and not matcher.matches(path):
                return False

        # Check attribute conditions
        if rule.conditions:
            if not file_attrs:
                # Cannot evaluate conditions without attributes
                return False

            if not self._evaluate_conditions(rule, file_attrs):
                return False

        # All checks passed
        return True

    def _evaluate_conditions(self, rule: Rule, file_attrs: Dict[str, Any]) -> bool:
        """Evaluate attribute conditions.

        Args:
            rule: Rule with conditions
            file_attrs: File attributes

        Returns:
            True if conditions match
        """
        if not rule.conditions:
            return True

        results = []
        for condition in rule.conditions:
            result = self._evaluate_condition(condition, file_attrs)
            results.append(result)

        # Apply logical operator
        if rule.condition_operator == RuleOperator.AND:
            return all(results)
        elif rule.condition_operator == RuleOperator.OR:
            return any(results)
        elif rule.condition_operator == RuleOperator.NOT:
            return not all(results)

        return False

    def _evaluate_condition(self, condition: Condition, file_attrs: Dict[str, Any]) -> bool:
        """Evaluate single condition.

        Args:
            condition: Condition to evaluate
            file_attrs: File attributes

        Returns:
            True if condition matches
        """
        # Get field value
        if condition.field not in file_attrs:
            return False

        actual = file_attrs[condition.field]
        expected = condition.value

        # Apply operator
        op = condition.operator.lower()

        if op == "eq" or op == "==":
            return actual == expected
        elif op == "ne" or op == "!=":
            return actual != expected
        elif op == "lt" or op == "<":
            return actual < expected
        elif op == "le" or op == "<=":
            return actual <= expected
        elif op == "gt" or op == ">":
            return actual > expected
        elif op == "ge" or op == ">=":
            return actual >= expected
        elif op == "contains":
            return expected in actual
        elif op == "startswith":
            return str(actual).startswith(str(expected))
        elif op == "endswith":
            return str(actual).endswith(str(expected))
        elif op == "matches":
            # Regex matching
            import re

            return bool(re.search(str(expected), str(actual)))

        return False

    def get_rules(self) -> List[Rule]:
        """Get all rules.

        Returns:
            List of rules
        """
        return self._rules.copy()

    def get_matching_rules(
        self, path: str, file_attrs: Optional[Dict[str, Any]] = None
    ) -> List[Rule]:
        """Get all rules that match the path.

        Args:
            path: File path
            file_attrs: File attributes

        Returns:
            List of matching rules
        """
        matches = []
        for rule in self._rules:
            if not rule.enabled:
                continue
            if self._evaluate_rule(rule, path, file_attrs):
                matches.append(rule)
        return matches

    def set_default_action(self, action: RuleAction) -> None:
        """Set default action when no rules match.

        Args:
            action: Default action
        """
        self._default_action = action

    def get_default_action(self) -> RuleAction:
        """Get default action.

        Returns:
            Default action
        """
        return self._default_action

    def enable_rule(self, name: str) -> bool:
        """Enable rule by name.

        Args:
            name: Rule name

        Returns:
            True if rule was found
        """
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = True
                return True
        return False

    def disable_rule(self, name: str) -> bool:
        """Disable rule by name.

        Args:
            name: Rule name

        Returns:
            True if rule was found
        """
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = False
                return True
        return False

    def __len__(self) -> int:
        """Return number of rules."""
        return len(self._rules)


def get_file_attrs(path: str) -> Dict[str, Any]:
    """Get file attributes for rule evaluation.

    Args:
        path: File path

    Returns:
        Dictionary of file attributes
    """
    try:
        st = os.stat(path)
        return {
            "size": st.st_size,
            "mtime": st.st_mtime,
            "ctime": st.st_ctime,
            "atime": st.st_atime,
            "mode": st.st_mode,
            "uid": st.st_uid,
            "gid": st.st_gid,
            "is_file": stat.S_ISREG(st.st_mode),
            "is_dir": stat.S_ISDIR(st.st_mode),
            "is_symlink": stat.S_ISLNK(st.st_mode),
            "permissions": stat.filemode(st.st_mode),
        }
    except (OSError, IOError):
        return {}
