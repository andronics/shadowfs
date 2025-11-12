"""Edge case tests for rule engine to improve coverage.

This module tests edge cases and error paths in the rule engine to cover:
- Line 203: Rule with no conditions returns True
- Line 218: Unknown condition operator returns False
- Line 264: Unknown comparison operator returns False
- Line 289: Disabled rule is skipped in get_matching_rules
"""
import pytest

from shadowfs.rules.engine import Condition, Rule, RuleAction, RuleEngine, RuleOperator


class TestRuleEngineEdgeCases:
    """Edge case tests for RuleEngine to improve coverage."""

    def test_rule_with_no_conditions_returns_true(self):
        """Test that rule with no conditions returns True (line 203)."""
        rule = Rule(
            action=RuleAction.INCLUDE,
            name="no-conditions",
            patterns=["*.py"],
        )

        engine = RuleEngine()
        # Directly test _evaluate_conditions with empty conditions list
        file_attrs = {"size": 1000}
        result = engine._evaluate_conditions(rule, file_attrs)

        # With no conditions, should return True
        assert result is True

    def test_disabled_rule_skipped_in_matching(self):
        """Test that disabled rules are skipped in get_matching_rules (line 289)."""
        # Add an enabled and a disabled rule
        enabled_rule = Rule(
            action=RuleAction.INCLUDE,
            name="enabled",
            patterns=["*.py"],
            enabled=True,
        )

        disabled_rule = Rule(
            action=RuleAction.INCLUDE,
            name="disabled",
            patterns=["*.py"],
            enabled=False,
        )

        engine = RuleEngine()
        engine.add_rule(enabled_rule)
        engine.add_rule(disabled_rule)

        # Get matching rules - should only return enabled rule
        matches = engine.get_matching_rules("test.py")
        assert len(matches) == 1
        assert matches[0].name == "enabled"

    def test_condition_with_unknown_operator_returns_false(self):
        """Test that unknown comparison operator returns False (line 264)."""
        # Create a condition with an unknown operator
        condition = Condition(field="size", operator="unknown_op", value=1000)

        engine = RuleEngine()
        file_attrs = {"size": 2000}

        # Unknown operator should return False
        result = engine._evaluate_condition(condition, file_attrs)
        assert result is False

    def test_invalid_condition_operator_returns_false(self):
        """Test that invalid condition operator returns False (line 218)."""
        rule = Rule(
            action=RuleAction.INCLUDE,
            name="test",
            patterns=["*.py"],
            conditions=[Condition(field="size", operator="gt", value=1000)],
        )

        # Manually set an invalid operator to test fallback
        rule.condition_operator = "INVALID"  # type: ignore

        engine = RuleEngine()
        file_attrs = {"size": 2000}

        # Invalid operator should return False
        result = engine._evaluate_conditions(rule, file_attrs)
        assert result is False
