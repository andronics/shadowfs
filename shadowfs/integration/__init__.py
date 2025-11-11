"""ShadowFS Integration Layer (Layer 3).

This layer integrates with external systems and provides core logic:
- PatternMatcher: Glob and regex pattern matching
- RuleEngine: File visibility rules evaluation
- TransformPipeline: Content transformation chain
- VirtualLayers: Multiple organizational views

These components build on Foundation (Layer 1) and Infrastructure (Layer 2)
and enable the Application Layer (Layer 4).
"""

from .pattern_matcher import MultiMatcher, PatternEntry, PatternMatcher, PatternType
from .rule_engine import Condition, Rule, RuleAction, RuleEngine, RuleOperator, get_file_attrs
from .transform_pipeline import TransformPipeline

__all__ = [
    # Pattern matching exports
    "PatternType",
    "PatternEntry",
    "PatternMatcher",
    "MultiMatcher",
    # Rule engine exports
    "RuleAction",
    "RuleOperator",
    "Condition",
    "Rule",
    "RuleEngine",
    "get_file_attrs",
    # Transform pipeline exports
    "TransformPipeline",
]
