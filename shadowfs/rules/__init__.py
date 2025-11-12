"""ShadowFS Rules System.

This module provides file visibility rules and pattern matching:
- PatternMatcher: Glob and regex pattern matching
- RuleEngine: File visibility rules evaluation

Rules control which files are visible in the ShadowFS mount point based on
configurable criteria like patterns, file attributes, and conditions.
"""

from .engine import Condition, Rule, RuleAction, RuleEngine, RuleOperator, get_file_attrs
from .patterns import MultiMatcher, PatternEntry, PatternMatcher, PatternType

__all__ = [
    # Pattern matching
    "PatternType",
    "PatternEntry",
    "PatternMatcher",
    "MultiMatcher",
    # Rule engine
    "RuleAction",
    "RuleOperator",
    "Condition",
    "Rule",
    "RuleEngine",
    "get_file_attrs",
]
