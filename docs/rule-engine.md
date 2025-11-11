# Advanced Rule Engine Extensions for ShadowFS

*Transforming the RuleEngine from basic filtering to intelligent decision-making*

---

## Overview

The ShadowFS RuleEngine currently provides solid pattern-based filtering with attribute conditions, logical operators, and priority-based evaluation. However, there's significant potential to extend it into a **comprehensive, intelligent decision engine** capable of temporal awareness, context sensitivity, machine learning, and sophisticated debugging.

This document explores 10 advanced rule engine patterns that would dramatically enhance filtering capabilities beyond simple pattern matching.

### Current Capabilities

**What the RuleEngine Does Well:**
- ✅ Pattern matching (glob and regex)
- ✅ Attribute conditions (size, date, permissions)
- ✅ Logical operators (AND, OR, NOT)
- ✅ Priority-based evaluation
- ✅ Runtime enable/disable
- ✅ First-match-wins strategy
- ✅ Excellent test coverage (99%+)

### Current Limitations

**What's Missing:**
- ❌ No temporal/scheduled rules
- ❌ No context awareness (user, network, system state)
- ❌ No rule chaining or composition
- ❌ No conflict detection
- ❌ Limited debugging ("Why is this hidden?")
- ❌ No rule templates or inheritance
- ❌ No external data integration
- ❌ No machine learning capabilities
- ❌ No performance optimization
- ❌ No dynamic rule modification

---

## 1. Dynamic Rule Modification Engine

### The Pattern

Enable hot-reloading and runtime modification of rules without filesystem remount or service restart.

### How It Works

```python
class DynamicRuleEngine(RuleEngine):
    """Rule engine with hot-reloadable rules."""

    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self.config_path = config_path
        self.config_watcher = None
        self.rule_versions: Dict[str, int] = {}  # Track rule changes

    def update_rule(self, rule_id: str, **updates) -> bool:
        """Modify rule attributes without removing/re-adding.

        Args:
            rule_id: Unique rule identifier
            **updates: Fields to update (priority, patterns, conditions, etc.)

        Returns:
            True if update successful
        """
        rule = self._get_rule_by_id(rule_id)
        if not rule:
            return False

        # Update fields
        for key, value in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        # Increment version
        self.rule_versions[rule_id] = self.rule_versions.get(rule_id, 0) + 1

        # Re-sort by priority
        self._sort_rules()

        # Invalidate caches that depend on this rule
        self._invalidate_caches(rule_id)

        logger.info(f"Updated rule {rule_id} to v{self.rule_versions[rule_id]}")
        return True

    def watch_config(self, config_path: str, callback=None):
        """Auto-reload rules from config file on change.

        Args:
            config_path: Path to YAML config file
            callback: Optional callback on reload
        """
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class ConfigChangeHandler(FileSystemEventHandler):
            def __init__(self, engine):
                self.engine = engine

            def on_modified(self, event):
                if event.src_path == config_path:
                    self.engine.reload_config(config_path)
                    if callback:
                        callback()

        self.config_watcher = Observer()
        handler = ConfigChangeHandler(self)
        self.config_watcher.schedule(handler, os.path.dirname(config_path))
        self.config_watcher.start()

    def reload_config(self, config_path: str) -> bool:
        """Hot-reload rules from configuration file.

        Atomically replaces current rule set with new one.
        """
        try:
            new_rules = self._parse_config(config_path)

            # Atomic swap
            old_rules = self._rules
            self._rules = new_rules

            # Clear caches
            self._clear_all_caches()

            logger.info(f"Reloaded {len(new_rules)} rules from {config_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
            # Keep old rules on error
            return False
```

### Configuration

```yaml
shadowfs:
  rule_engine:
    hot_reload: true
    config_watch: true
    reload_interval: 5  # Check every 5 seconds

    # Versioning for A/B testing
    versioning:
      enabled: true
      track_history: true
      max_versions: 10
```

### Use Cases

1. **Zero-downtime updates**: Change rules without unmounting filesystem
2. **A/B testing**: Test rule variations in production
3. **Emergency responses**: Quickly adjust rules during incidents
4. **Gradual rollouts**: Deploy rule changes incrementally

### Implementation Complexity

**Medium** - Requires:
- File watching infrastructure
- Atomic rule swapping
- Cache invalidation strategies
- Backward compatibility handling

### Integration

- Hooks into `config_manager.py` hot-reload system
- Triggers `cache_manager.py` invalidation
- Emits events via event system for monitoring

---

## 2. Temporal Rule Scheduler

### The Pattern

Enable time-based rule activation with cron-like scheduling, validity windows, and dynamic time expressions.

### How It Works

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import pytz

@dataclass
class TemporalRule(Rule):
    """Rule with time-based activation."""

    schedule: Optional[str] = None  # Cron expression: "0 9-17 * * 1-5"
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    timezone: str = "UTC"

    def is_active_at(self, time: datetime) -> bool:
        """Check if rule is active at given time."""
        tz = pytz.timezone(self.timezone)
        time = time.astimezone(tz)

        # Check validity window
        if self.valid_from and time < self.valid_from:
            return False
        if self.valid_until and time > self.valid_until:
            return False

        # Check cron schedule
        if self.schedule:
            from croniter import croniter
            cron = croniter(self.schedule, time)
            # Check if current time matches schedule
            return cron.match(time)

        return True


class TemporalRuleEngine(RuleEngine):
    """Rule engine with time-based filtering."""

    def __init__(self, timezone: str = "UTC"):
        super().__init__()
        self.timezone = timezone
        self._active_rules_cache = None
        self._cache_time = None
        self._cache_ttl = 60  # Re-evaluate active rules every minute

    def should_show(self, path: str, attrs: Dict[str, Any]) -> bool:
        current_time = datetime.now(pytz.timezone(self.timezone))

        # Get currently active rules (cached for performance)
        active_rules = self._get_active_rules(current_time)

        # Evaluate only active rules
        return self._evaluate_rules(active_rules, path, attrs)

    def _get_active_rules(self, current_time: datetime) -> List[Rule]:
        """Get rules active at current time (with caching)."""
        # Check cache validity
        if (self._active_rules_cache is not None and
            self._cache_time is not None and
            (current_time - self._cache_time).total_seconds() < self._cache_ttl):
            return self._active_rules_cache

        # Filter rules by time validity
        active = []
        for rule in self._rules:
            if isinstance(rule, TemporalRule):
                if rule.is_active_at(current_time):
                    active.append(rule)
            else:
                # Regular rules always active
                active.append(rule)

        # Cache results
        self._active_rules_cache = active
        self._cache_time = current_time

        return active


class DynamicTimeExpression:
    """Parse dynamic time expressions like 'now - 30 days'."""

    @staticmethod
    def parse(expression: str) -> datetime:
        """Parse expression into datetime.

        Examples:
            - "now"
            - "now - 30 days"
            - "now - 2 weeks"
            - "2024-01-01"
        """
        if expression == "now":
            return datetime.now()

        if " - " in expression:
            # Parse "now - X units"
            parts = expression.split(" - ")
            if parts[0].strip() == "now":
                delta_parts = parts[1].strip().split()
                value = int(delta_parts[0])
                unit = delta_parts[1].lower()

                if unit in ["day", "days"]:
                    return datetime.now() - timedelta(days=value)
                elif unit in ["week", "weeks"]:
                    return datetime.now() - timedelta(weeks=value)
                elif unit in ["hour", "hours"]:
                    return datetime.now() - timedelta(hours=value)

        # Parse ISO date
        return datetime.fromisoformat(expression)
```

### Configuration

```yaml
rules:
  # Work hours only
  - name: "Hide personal files during work"
    action: exclude
    patterns: ["*/personal/**"]
    schedule: "0 9-17 * * 1-5"  # 9am-5pm, Mon-Fri
    timezone: "America/New_York"

  # Temporary rule with expiration
  - name: "Hide project during migration"
    action: exclude
    patterns: ["*/old-project/**"]
    valid_from: "2024-11-01T00:00:00"
    valid_until: "2024-12-01T00:00:00"

  # Dynamic time expression
  - name: "Hide old logs"
    action: exclude
    patterns: ["**/logs/**"]
    conditions:
      - field: mtime
        operator: lt
        value: "now - 30 days"  # Files older than 30 days
```

### Use Cases

1. **Work/home separation**: Hide work files outside office hours
2. **Automated cleanup**: Hide old files after retention period
3. **Seasonal content**: Show holiday themes during December
4. **Maintenance windows**: Hide directories during backup
5. **Time-limited access**: Temporary project visibility

### Implementation Complexity

**Medium-High** - Requires:
- Cron parser (croniter library)
- Timezone handling (pytz)
- Dynamic expression parser
- Active rule caching for performance

### Integration

- Cache active rules (invalidate every minute)
- Log rule activation/deactivation events
- Metrics for temporal rule effectiveness

---

## 3. Context-Aware Rule Engine

### The Pattern

Rules that adapt based on runtime context: current user, network location, system state, environment variables, and more.

### How It Works

```python
@dataclass
class ContextualRule(Rule):
    """Rule that depends on runtime context."""

    context_requirements: Dict[str, Any] = field(default_factory=dict)
    # Examples:
    # - user: ["alice", "bob"]
    # - network: "corporate"
    # - disk_usage_gt: 90
    # - battery_level_lt: 20
    # - git_branch: "main"


class ContextProvider:
    """Supplies runtime context information."""

    def get_context(self) -> Dict[str, Any]:
        """Gather all available context."""
        return {
            "user": self._get_current_user(),
            "hostname": socket.gethostname(),
            "network": self._detect_network(),
            "disk_usage": self._get_disk_usage(),
            "battery_level": self._get_battery_level(),
            "load_average": os.getloadavg()[0],
            "git_branch": self._get_git_branch(),
            "env": dict(os.environ),
        }

    def _get_current_user(self) -> str:
        """Get current username."""
        return os.getenv("USER") or os.getenv("USERNAME") or "unknown"

    def _detect_network(self) -> str:
        """Detect network type (corporate, home, public)."""
        # Check WiFi SSID, VPN status, DNS servers, etc.
        import subprocess
        try:
            # Check if VPN is active
            output = subprocess.check_output(["ip", "route"], text=True)
            if "tun0" in output or "vpn" in output:
                return "corporate"
        except:
            pass

        return "unknown"

    def _get_disk_usage(self) -> float:
        """Get disk usage percentage."""
        import shutil
        stats = shutil.disk_usage("/")
        return (stats.used / stats.total) * 100

    def _get_battery_level(self) -> Optional[int]:
        """Get battery level (laptops only)."""
        try:
            with open("/sys/class/power_supply/BAT0/capacity", "r") as f:
                return int(f.read().strip())
        except:
            return None

    def _get_git_branch(self) -> Optional[str]:
        """Get current git branch if in repo."""
        try:
            import subprocess
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            return branch
        except:
            return None


class ContextAwareRuleEngine(RuleEngine):
    """Rule engine with context-based filtering."""

    def __init__(self, context_provider: Optional[ContextProvider] = None):
        super().__init__()
        self.context_provider = context_provider or ContextProvider()
        self._context_cache = None
        self._context_cache_time = None
        self._context_cache_ttl = 10  # Cache for 10 seconds

    def should_show(self, path: str, attrs: Dict[str, Any]) -> bool:
        # Get current context (cached)
        current_context = self._get_cached_context()

        # Filter rules by context match
        applicable_rules = [
            r for r in self._rules
            if self._context_matches(r, current_context)
        ]

        # Evaluate applicable rules
        return self._evaluate_rules(applicable_rules, path, attrs)

    def _get_cached_context(self) -> Dict[str, Any]:
        """Get context with caching to avoid expensive operations."""
        now = time.time()

        if (self._context_cache is not None and
            self._context_cache_time is not None and
            (now - self._context_cache_time) < self._context_cache_ttl):
            return self._context_cache

        # Refresh context
        self._context_cache = self.context_provider.get_context()
        self._context_cache_time = now

        return self._context_cache

    def _context_matches(self, rule: Rule, ctx: Dict[str, Any]) -> bool:
        """Check if rule's context requirements match current context."""
        if not isinstance(rule, ContextualRule):
            return True  # Regular rules always apply

        for key, required_value in rule.context_requirements.items():
            # Handle comparison operators
            if key.endswith("_gt"):
                field = key[:-3]
                if ctx.get(field, 0) <= required_value:
                    return False
            elif key.endswith("_lt"):
                field = key[:-3]
                if ctx.get(field, float('inf')) >= required_value:
                    return False
            elif key.endswith("_gte"):
                field = key[:-4]
                if ctx.get(field, 0) < required_value:
                    return False
            elif key.endswith("_lte"):
                field = key[:-4]
                if ctx.get(field, float('inf')) > required_value:
                    return False
            else:
                # Exact match or list membership
                ctx_value = ctx.get(key)
                if isinstance(required_value, list):
                    if ctx_value not in required_value:
                        return False
                else:
                    if ctx_value != required_value:
                        return False

        return True
```

### Configuration

```yaml
rules:
  # User-specific hiding
  - name: "Hide admin files from regular users"
    action: exclude
    patterns: ["*/admin/**"]
    context:
      user: ["alice", "bob"]  # Only hide for these users

  # Network-based filtering
  - name: "Hide personal files on corporate network"
    action: exclude
    patterns: ["*/personal/**", "*/private/**"]
    context:
      network: "corporate"

  # Resource-constrained hiding
  - name: "Aggressive cleanup when disk full"
    action: exclude
    patterns: ["**/.cache/**", "**/tmp/**", "**/__pycache__/**"]
    context:
      disk_usage_gt: 90  # Only when disk > 90% full

  # Battery-aware (laptops)
  - name: "Hide heavy files on low battery"
    action: exclude
    patterns: ["**/videos/**"]
    context:
      battery_level_lt: 20

  # Git-aware
  - name: "Hide feature branches except current"
    action: exclude
    patterns: ["*/branches/feature-*"]
    context:
      git_branch: "main"  # Only on main branch
```

### Use Cases

1. **Multi-tenant systems**: Different rules per user/team
2. **Mobile/laptop**: Different rules based on network (home vs. corporate)
3. **Resource management**: Aggressive hiding when disk/memory low
4. **Project awareness**: Show only files for current Git branch
5. **Location-based**: Different rules at home vs. office
6. **Battery optimization**: Hide heavy files when battery low

### Implementation Complexity

**High** - Requires:
- Context detection mechanisms
- Performance optimization (context caching critical)
- Security (prevent context spoofing)
- Cross-platform support (battery, network detection)

### Integration

- New `context_provider.py` in Infrastructure layer
- Cache context per evaluation cycle
- Metrics on context-based rule activation
- Security: validate context sources

---

## 4. Rule Conflict Detection and Resolution

### The Pattern

Detect when multiple rules conflict for the same file and provide intelligent resolution strategies beyond simple priority.

### How It Works

```python
from enum import Enum

class ConflictResolution(Enum):
    """Strategies for resolving rule conflicts."""

    PRIORITY = "priority"  # Highest priority wins (current default)
    SPECIFICITY = "specificity"  # Most specific pattern wins
    MOST_RESTRICTIVE = "most_restrictive"  # EXCLUDE wins over INCLUDE
    LEAST_RESTRICTIVE = "least_restrictive"  # INCLUDE wins over EXCLUDE
    FIRST_DEFINED = "first_defined"  # Order in config file
    MOST_RECENT = "most_recent"  # Last modified rule
    CUSTOM = "custom"  # User-defined resolver function


@dataclass
class RuleConflict:
    """Record of a rule conflict."""

    path: str
    conflicting_rules: List[Rule]
    resolution_strategy: ConflictResolution
    winner: Rule
    timestamp: datetime


class ConflictAwareRuleEngine(RuleEngine):
    """Rule engine with conflict detection and resolution."""

    def __init__(self, conflict_strategy: ConflictResolution = ConflictResolution.PRIORITY):
        super().__init__()
        self.conflict_strategy = conflict_strategy
        self.conflict_log: List[RuleConflict] = []
        self.conflict_threshold = 100  # Warn after 100 conflicts

    def should_show(self, path: str, attrs: Dict[str, Any]) -> bool:
        # Find ALL matching rules (not just first)
        matching_rules = self.get_matching_rules(path, attrs)

        if len(matching_rules) == 0:
            return self._default_action == RuleAction.INCLUDE

        if len(matching_rules) == 1:
            return matching_rules[0].action == RuleAction.INCLUDE

        # CONFLICT DETECTED - multiple rules match
        winner = self._resolve_conflict(matching_rules, path)

        # Log conflict
        self._log_conflict(path, matching_rules, winner)

        return winner.action == RuleAction.INCLUDE

    def get_matching_rules(self, path: str, attrs: Dict[str, Any]) -> List[Rule]:
        """Find all rules that match the given path/attributes."""
        matching = []
        for rule in self._rules:
            if not rule.enabled:
                continue

            if self._evaluate_rule(rule, path, attrs):
                matching.append(rule)

        return matching

    def _resolve_conflict(self, rules: List[Rule], path: str) -> Rule:
        """Resolve conflict using configured strategy."""
        if self.conflict_strategy == ConflictResolution.PRIORITY:
            return max(rules, key=lambda r: r.priority)

        elif self.conflict_strategy == ConflictResolution.SPECIFICITY:
            return self._most_specific_rule(rules, path)

        elif self.conflict_strategy == ConflictResolution.MOST_RESTRICTIVE:
            # EXCLUDE wins over INCLUDE
            for r in rules:
                if r.action == RuleAction.EXCLUDE:
                    return r
            return rules[0]

        elif self.conflict_strategy == ConflictResolution.LEAST_RESTRICTIVE:
            # INCLUDE wins over EXCLUDE
            for r in rules:
                if r.action == RuleAction.INCLUDE:
                    return r
            return rules[0]

        elif self.conflict_strategy == ConflictResolution.FIRST_DEFINED:
            # Return first rule in original order
            return min(rules, key=lambda r: self._rules.index(r))

        else:  # PRIORITY as fallback
            return max(rules, key=lambda r: r.priority)

    def _most_specific_rule(self, rules: List[Rule], path: str) -> Rule:
        """Calculate specificity score and return most specific rule.

        Specificity scoring:
        - More conditions = higher score
        - More specific patterns = higher score
        - Exact path match > directory match > wildcard
        """
        scored = [(self._specificity_score(r, path), r) for r in rules]
        return max(scored, key=lambda x: x[0])[1]

    def _specificity_score(self, rule: Rule, path: str) -> int:
        """Calculate specificity score for a rule."""
        score = 0

        # Condition count (each condition adds 10 points)
        score += len(rule.conditions) * 10

        # Pattern specificity
        for pattern in rule.patterns:
            if pattern == path:
                score += 100  # Exact match
            elif '**' not in pattern and '*' not in pattern:
                score += 50  # No wildcards
            elif '**' not in pattern:
                score += 25  # Single-level wildcard only
            else:
                score += 5  # Recursive wildcard

        return score

    def _log_conflict(self, path: str, rules: List[Rule], winner: Rule):
        """Log conflict for debugging."""
        conflict = RuleConflict(
            path=path,
            conflicting_rules=rules,
            resolution_strategy=self.conflict_strategy,
            winner=winner,
            timestamp=datetime.now()
        )

        self.conflict_log.append(conflict)

        # Warn if too many conflicts
        if len(self.conflict_log) >= self.conflict_threshold:
            logger.warning(
                f"High conflict rate: {len(self.conflict_log)} conflicts. "
                "Consider reviewing rule configuration."
            )

    def get_conflicts(self, path: Optional[str] = None) -> List[RuleConflict]:
        """Get conflict log, optionally filtered by path."""
        if path:
            return [c for c in self.conflict_log if c.path == path]
        return self.conflict_log

    def get_conflict_report(self) -> Dict[str, Any]:
        """Generate conflict statistics report."""
        total = len(self.conflict_log)
        if total == 0:
            return {"total_conflicts": 0}

        # Count by path
        by_path = {}
        for conflict in self.conflict_log:
            by_path[conflict.path] = by_path.get(conflict.path, 0) + 1

        # Most conflicted paths
        top_conflicts = sorted(by_path.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total_conflicts": total,
            "unique_paths": len(by_path),
            "avg_conflicts_per_path": total / len(by_path),
            "top_conflicted_paths": top_conflicts,
            "resolution_strategy": self.conflict_strategy.value,
        }
```

### Configuration

```yaml
shadowfs:
  rule_engine:
    conflict_resolution: specificity  # or priority, most_restrictive, etc.
    log_conflicts: true
    conflict_threshold: 100  # Warn after 100 conflicts
    conflict_report_interval: 3600  # Generate report every hour

rules:
  # These rules conflict for "test_module.py"
  - name: "Include all Python files"
    action: include
    patterns: ["*.py"]
    priority: 10

  - name: "Exclude test files"
    action: exclude
    patterns: ["test_*.py"]
    priority: 20

  # Resolution with 'specificity': "Exclude test files" wins (more specific pattern)
  # Resolution with 'priority': "Exclude test files" wins (higher priority)
  # Resolution with 'most_restrictive': "Exclude test files" wins (EXCLUDE over INCLUDE)
```

### Use Cases

1. **Debugging**: "Why is this file hidden when I have an include rule?"
2. **Complex rule sets**: Large configurations with overlapping rules
3. **Team collaboration**: Different developers adding conflicting rules
4. **Security-first**: Most restrictive always wins
5. **User-friendly**: Least restrictive wins for better UX
6. **Audit compliance**: Log all conflicts for review

### Implementation Complexity

**Medium** - Requires:
- Finding all matching rules (not just first)
- Specificity calculation algorithm
- Conflict logging infrastructure
- Performance considerations (caching)

### Integration

- New `conflict_resolver.py` component
- Enhanced logging with conflict reports
- Control API: `/conflicts` endpoint for analysis
- Metrics: conflicts per 1000 evaluations

---

## 5. Rule Chain and Composition Engine

### The Pattern

Create complex rules by chaining and composing simpler rules, enabling DRY principles and sophisticated logic.

### How It Works

```python
@dataclass
class CompositeRule(Rule):
    """Rule composed of other rules."""

    subrules: List[Rule] = field(default_factory=list)
    composition_operator: RuleOperator = RuleOperator.AND

    def add_subrule(self, rule: Rule):
        """Add a subrule to this composite."""
        self.subrules.append(rule)


@dataclass
class ChainedRule(Rule):
    """Rule that depends on other rules."""

    depends_on: List[str] = field(default_factory=list)  # Rule names/IDs
    dependency_operator: RuleOperator = RuleOperator.AND


class ComposableRuleEngine(RuleEngine):
    """Rule engine supporting composition and chaining."""

    def __init__(self):
        super().__init__()
        self.rule_registry: Dict[str, Rule] = {}  # name -> rule
        self.dependency_graph = {}  # For cycle detection

    def add_rule(self, rule: Rule) -> bool:
        """Add rule and register it for composition."""
        # Register named rules
        if rule.name:
            self.rule_registry[rule.name] = rule

        # Build dependency graph for chained rules
        if isinstance(rule, ChainedRule):
            self.dependency_graph[rule.name] = rule.depends_on

            # Check for cycles
            if self._has_cycle(rule.name):
                logger.error(f"Cycle detected in rule dependencies for {rule.name}")
                return False

        return super().add_rule(rule)

    def _evaluate_rule(self, rule: Rule, path: str, attrs: Dict[str, Any]) -> bool:
        """Evaluate rule with composition and chaining support."""
        # Handle composite rules
        if isinstance(rule, CompositeRule):
            return self._evaluate_composite(rule, path, attrs)

        # Handle chained rules
        if isinstance(rule, ChainedRule):
            return self._evaluate_chained(rule, path, attrs)

        # Regular rule evaluation
        return super()._evaluate_rule(rule, path, attrs)

    def _evaluate_composite(self, rule: CompositeRule, path: str, attrs: Dict[str, Any]) -> bool:
        """Evaluate composite rule by combining subrule results."""
        if not rule.subrules:
            return False

        results = [
            self._evaluate_rule(subrule, path, attrs)
            for subrule in rule.subrules
        ]

        if rule.composition_operator == RuleOperator.AND:
            return all(results)
        elif rule.composition_operator == RuleOperator.OR:
            return any(results)
        else:  # NOT
            return not all(results)

    def _evaluate_chained(self, rule: ChainedRule, path: str, attrs: Dict[str, Any]) -> bool:
        """Evaluate chained rule by first evaluating dependencies."""
        # Evaluate dependencies first
        dep_results = []
        for dep_name in rule.depends_on:
            dep_rule = self.rule_registry.get(dep_name)
            if not dep_rule:
                logger.warning(f"Dependency {dep_name} not found for rule {rule.name}")
                return False

            dep_result = self._evaluate_rule(dep_rule, path, attrs)
            dep_results.append(dep_result)

        # Check if dependencies pass
        if rule.dependency_operator == RuleOperator.AND:
            if not all(dep_results):
                return False
        elif rule.dependency_operator == RuleOperator.OR:
            if not any(dep_results):
                return False

        # Dependencies passed, evaluate main rule
        return super()._evaluate_rule(rule, path, attrs)

    def _has_cycle(self, rule_name: str, visited: Optional[Set] = None) -> bool:
        """Check for cycles in dependency graph (DFS)."""
        if visited is None:
            visited = set()

        if rule_name in visited:
            return True  # Cycle detected

        visited.add(rule_name)

        for dep in self.dependency_graph.get(rule_name, []):
            if self._has_cycle(dep, visited):
                return True

        visited.remove(rule_name)
        return False

    def get_rule_by_name(self, name: str) -> Optional[Rule]:
        """Retrieve rule by name from registry."""
        return self.rule_registry.get(name)
```

### Configuration

```yaml
rules:
  # Base rules (building blocks)
  - name: "is_large_file"
    action: include
    conditions:
      - field: size
        operator: gt
        value: 10485760  # 10MB

  - name: "is_media_file"
    action: include
    patterns: ["*.mp4", "*.mkv", "*.avi", "*.mov"]

  - name: "is_old_file"
    action: include
    conditions:
      - field: mtime
        operator: lt
        value: "now - 90 days"

  # Composite rules (combine base rules)
  - name: "large_media_files"
    action: exclude
    type: composite
    operator: and
    subrules:
      - is_large_file
      - is_media_file

  - name: "old_or_large"
    action: exclude
    type: composite
    operator: or
    subrules:
      - is_old_file
      - is_large_file

  # Chained rule (conditional logic)
  - name: "hide_backup_if_original_exists"
    action: exclude
    patterns: ["*.bak", "*.backup"]
    type: chained
    depends_on:
      - original_file_exists  # Custom rule that checks filesystem
    dependency_operator: and
```

### Use Cases

1. **DRY principles**: Reuse common rule components across multiple rules
2. **Complex logic**: "(Large AND media) OR (temp AND old)"
3. **Conditional hiding**: "Hide .bak only if original exists"
4. **Rule libraries**: Share common rules across projects
5. **Maintainability**: Change one base rule → affects all compositions
6. **Readability**: Named components more understandable than inline logic

### Implementation Complexity

**Medium-High** - Requires:
- Dependency graph management
- Cycle detection (prevent infinite recursion)
- Evaluation order optimization
- Rule registry and lookup
- Recursive evaluation

### Integration

- DAG (Directed Acyclic Graph) for dependency validation
- Rule result caching for composed rules
- Enhanced config schema for composition syntax
- Documentation generator for composed rules

---

## 6. External Data Integration Layer

### The Pattern

Enable rules to query external data sources (APIs, databases, Git metadata, scripts) for dynamic decision-making.

### How It Works

```python
@dataclass
class ExternalCondition(Condition):
    """Condition that queries external data."""

    source_type: str  # "api", "db", "file", "git", "script"
    source_config: Dict[str, Any]
    cache_ttl: int = 300  # Cache results for 5 minutes
    timeout: int = 5  # Query timeout in seconds


class DataSource(ABC):
    """Abstract base class for external data sources."""

    @abstractmethod
    async def query(self, config: Dict[str, Any], attrs: Dict[str, Any]) -> Any:
        """Query the data source."""
        pass


class GitDataSource(DataSource):
    """Query Git metadata."""

    def __init__(self, repo_path: str):
        import git
        self.repo = git.Repo(repo_path)

    async def query(self, config: Dict[str, Any], attrs: Dict[str, Any]) -> Any:
        """Query git metadata for a file."""
        path = attrs.get("path")
        field = config.get("field")

        if field == "author":
            return self._get_last_author(path)
        elif field == "last_commit_date":
            return self._get_last_commit_date(path)
        elif field == "branch":
            return self.repo.active_branch.name
        elif field == "is_tracked":
            return path in self.repo.git.ls_files()

        return None

    def _get_last_author(self, path: str) -> Optional[str]:
        """Get the author of the last commit for this file."""
        try:
            commits = list(self.repo.iter_commits(paths=path, max_count=1))
            if commits:
                return commits[0].author.email
        except:
            pass
        return None


class APIDataSource(DataSource):
    """Query REST APIs."""

    def __init__(self, base_url: str, auth_token: Optional[str] = None):
        self.base_url = base_url
        self.auth_token = auth_token
        self.session = aiohttp.ClientSession()

    async def query(self, config: Dict[str, Any], attrs: Dict[str, Any]) -> Any:
        """Query REST API."""
        endpoint = config.get("endpoint")
        url = f"{self.base_url}{endpoint}".format(**attrs)

        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        try:
            async with self.session.get(url, headers=headers, timeout=config.get("timeout", 5)) as response:
                data = await response.json()
                return data.get(config.get("field"))
        except Exception as e:
            logger.error(f"API query failed: {e}")
            return None


class DatabaseDataSource(DataSource):
    """Query SQL databases."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    async def query(self, config: Dict[str, Any], attrs: Dict[str, Any]) -> Any:
        """Execute SQL query."""
        import aiosqlite

        query = config.get("query")
        params = {k: attrs.get(k) for k in config.get("params", [])}

        try:
            async with aiosqlite.connect(self.connection_string) as db:
                async with db.execute(query, params) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return row[0]
        except Exception as e:
            logger.error(f"Database query failed: {e}")

        return None


class ExternalDataRuleEngine(RuleEngine):
    """Rule engine with external data integration."""

    def __init__(self, data_sources: Dict[str, DataSource]):
        super().__init__()
        self.data_sources = data_sources
        self.external_cache = TTLCache(maxsize=10000, ttl=300)

    async def should_show_async(self, path: str, attrs: Dict[str, Any]) -> bool:
        """Async version for external data queries."""
        for rule in self._rules:
            if not rule.enabled:
                continue

            # Check for external conditions
            has_external = any(
                isinstance(c, ExternalCondition) for c in rule.conditions
            )

            if has_external:
                matched = await self._evaluate_rule_async(rule, path, attrs)
            else:
                matched = self._evaluate_rule(rule, path, attrs)

            if matched:
                return rule.action == RuleAction.INCLUDE

        return self._default_action == RuleAction.INCLUDE

    async def _evaluate_rule_async(self, rule: Rule, path: str, attrs: Dict[str, Any]) -> bool:
        """Evaluate rule with async external queries."""
        # Pattern matching (sync)
        pattern_match = self._evaluate_patterns(rule, path)
        if not pattern_match:
            return False

        # Condition evaluation (may be async)
        condition_tasks = []
        for condition in rule.conditions:
            if isinstance(condition, ExternalCondition):
                task = self._evaluate_external_condition(condition, attrs)
                condition_tasks.append(task)
            else:
                # Regular condition (sync)
                result = self._evaluate_condition(condition, attrs)
                condition_tasks.append(asyncio.coroutine(lambda: result)())

        # Wait for all conditions
        results = await asyncio.gather(*condition_tasks)

        # Combine with logical operator
        if rule.condition_operator == RuleOperator.AND:
            return all(results)
        else:  # OR
            return any(results)

    async def _evaluate_external_condition(self, cond: ExternalCondition, attrs: Dict[str, Any]) -> bool:
        """Evaluate condition with external data query."""
        # Check cache
        cache_key = f"{cond.source_type}:{cond.field}:{attrs.get('path')}"
        if cache_key in self.external_cache:
            cached_value = self.external_cache[cache_key]
        else:
            # Query external source
            source = self.data_sources.get(cond.source_type)
            if not source:
                logger.warning(f"Data source {cond.source_type} not found")
                return False

            try:
                cached_value = await asyncio.wait_for(
                    source.query(cond.source_config, attrs),
                    timeout=cond.timeout
                )
                self.external_cache[cache_key] = cached_value
            except asyncio.TimeoutError:
                logger.warning(f"External query timeout for {cache_key}")
                return False
            except Exception as e:
                logger.error(f"External query error: {e}")
                return False

        # Compare with condition value
        return self._compare_values(cached_value, cond.operator, cond.value)
```

### Configuration

```yaml
data_sources:
  git:
    type: git
    repo_path: /source

  content_api:
    type: api
    base_url: https://api.example.com
    auth_token: ${CONTENT_API_TOKEN}

  metadata_db:
    type: database
    connection_string: sqlite:///metadata.db

rules:
  # Git-aware filtering
  - name: "Hide files by specific author"
    action: exclude
    patterns: ["**/*"]
    conditions:
      - field: git_author
        operator: eq
        value: "john.doe@example.com"
        source_type: git
        source_config:
          field: author
        cache_ttl: 600

  # API-based content classification
  - name: "Hide NSFW images"
    action: exclude
    patterns: ["**/*.jpg", "**/*.png"]
    conditions:
      - field: content_rating
        operator: eq
        value: "nsfw"
        source_type: api
        source_config:
          endpoint: "/classify?path={path}"
          field: rating
        cache_ttl: 86400  # Cache for 1 day
        timeout: 10

  # Database lookup
  - name: "Hide files in blocklist"
    action: exclude
    patterns: ["**/*"]
    conditions:
      - field: is_blocked
        operator: eq
        value: true
        source_type: database
        source_config:
          query: "SELECT blocked FROM files WHERE path = :path"
          params: ["path"]
        cache_ttl: 300
```

### Use Cases

1. **Git-aware filtering**: Hide files by author, branch, or last commit
2. **Content classification**: Query ML API to classify images/documents
3. **Database lookups**: Check if file is in approved/denied list
4. **Script integration**: Run custom logic to determine visibility
5. **Cloud metadata**: Query S3 tags, Google Drive labels
6. **Compliance**: Check external approval systems

### Implementation Complexity

**High** - Requires:
- Multiple data source adapters
- Async query execution
- Comprehensive error handling
- Timeout management
- Security (credential management)
- Performance (aggressive caching essential)

### Integration

- New `data_sources/` package in Integration layer
- Async operations throughout rule engine
- Connection pooling for databases/APIs
- Metrics for external query latency and error rates
- Circuit breaker pattern for failing sources

---

## 7. Machine Learning Rule Generator

### The Pattern

Automatically learn and generate rules by analyzing user access patterns and file characteristics.

### How It Works

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier


@dataclass
class AccessRecord:
    """Record of a file access decision."""

    path: str
    file_attrs: Dict[str, Any]
    shown: bool  # Was file visible?
    accessed: bool  # Was file actually opened/read?
    timestamp: datetime


class AccessLog:
    """Log of file access patterns."""

    def __init__(self):
        self.records: List[AccessRecord] = []

    def record(self, path: str, attrs: Dict[str, Any], shown: bool, accessed: bool = False):
        """Record an access decision."""
        self.records.append(AccessRecord(
            path=path,
            file_attrs=attrs,
            shown=shown,
            accessed=accessed,
            timestamp=datetime.now()
        ))

    def mark_accessed(self, path: str):
        """Mark that a file was actually accessed."""
        for record in reversed(self.records):
            if record.path == path:
                record.accessed = True
                break

    def get_training_data(self, window_days: int = 30) -> pd.DataFrame:
        """Get training data from recent access log."""
        cutoff = datetime.now() - timedelta(days=window_days)
        recent = [r for r in self.records if r.timestamp >= cutoff]

        # Convert to DataFrame
        data = []
        for record in recent:
            row = {
                **record.file_attrs,
                'accessed': record.accessed,
            }
            data.append(row)

        return pd.DataFrame(data)


class MLRuleGenerator:
    """Generate rules by learning from access patterns."""

    def __init__(self, access_log: AccessLog, model_type: str = "decision_tree"):
        self.access_log = access_log
        self.model_type = model_type
        self.model = None
        self.feature_names = None

    def train(self, training_window_days: int = 30):
        """Train model on access log data."""
        df = self.access_log.get_training_data(training_window_days)

        if len(df) < 100:
            logger.warning("Insufficient training data (< 100 records)")
            return False

        # Extract features
        X, self.feature_names = self._extract_features(df)
        y = df['accessed'].values  # 1 = accessed, 0 = never accessed

        # Train model
        if self.model_type == "decision_tree":
            self.model = DecisionTreeClassifier(max_depth=5, min_samples_split=10)
        elif self.model_type == "random_forest":
            self.model = RandomForestClassifier(n_estimators=10, max_depth=5)

        self.model.fit(X, y)

        logger.info(f"Trained {self.model_type} on {len(df)} records")
        return True

    def _extract_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Extract numeric features from file attributes."""
        features = []
        feature_names = []

        # Numeric features
        if 'size' in df.columns:
            features.append(df['size'].values)
            feature_names.append('size')

        if 'mtime' in df.columns:
            # Convert to days old
            now = datetime.now()
            days_old = [(now - pd.to_datetime(t)).days for t in df['mtime']]
            features.append(days_old)
            feature_names.append('days_old')

        # Categorical features (one-hot encoding)
        if 'extension' in df.columns:
            extensions = pd.get_dummies(df['extension'], prefix='ext')
            features.append(extensions.values)
            feature_names.extend(extensions.columns)

        return np.column_stack(features), feature_names

    def generate_rules(self, min_confidence: float = 0.8) -> List[Rule]:
        """Extract rules from trained model."""
        if not self.model:
            return []

        if self.model_type == "decision_tree":
            return self._extract_tree_rules(min_confidence)
        elif self.model_type == "random_forest":
            return self._extract_forest_rules(min_confidence)

        return []

    def _extract_tree_rules(self, min_confidence: float) -> List[Rule]:
        """Extract rules from decision tree."""
        from sklearn.tree import _tree

        tree = self.model.tree_
        rules = []

        def recurse(node, path_conditions):
            if tree.feature[node] != _tree.TREE_UNDEFINED:
                # Decision node
                feature = self.feature_names[tree.feature[node]]
                threshold = tree.threshold[node]

                # Left branch (<=)
                left_conditions = path_conditions + [(feature, "<=", threshold)]
                recurse(tree.children_left[node], left_conditions)

                # Right branch (>)
                right_conditions = path_conditions + [(feature, ">", threshold)]
                recurse(tree.children_right[node], right_conditions)
            else:
                # Leaf node - extract rule
                samples = tree.n_node_samples[node]
                value = tree.value[node][0]
                confidence = value[1] / samples  # Probability of "accessed"

                if confidence >= min_confidence:
                    rule = self._conditions_to_rule(path_conditions, confidence)
                    if rule:
                        rules.append(rule)

        recurse(0, [])
        return rules

    def _conditions_to_rule(self, conditions: List[Tuple], confidence: float) -> Optional[Rule]:
        """Convert decision path to Rule object."""
        if not conditions:
            return None

        # Create conditions
        rule_conditions = []
        for feature, op, value in conditions:
            if feature == 'size':
                rule_conditions.append(Condition(
                    field='size',
                    operator='lt' if op == '<=' else 'gt',
                    value=int(value)
                ))
            elif feature == 'days_old':
                rule_conditions.append(Condition(
                    field='mtime',
                    operator='lt' if op == '<=' else 'gt',
                    value=f"now - {int(value)} days"
                ))

        if not rule_conditions:
            return None

        return Rule(
            name=f"learned_{hash(tuple(conditions))}",
            action=RuleAction.EXCLUDE,  # Hide never-accessed files
            patterns=["**/*"],
            conditions=rule_conditions,
            priority=-100,  # Low priority
            metadata={'confidence': confidence, 'source': 'ml'}
        )


class AdaptiveRuleEngine(RuleEngine):
    """Rule engine that learns from usage patterns."""

    def __init__(self, enable_learning: bool = True, learning_interval_days: int = 7):
        super().__init__()
        self.enable_learning = enable_learning
        self.learning_interval = timedelta(days=learning_interval_days)
        self.access_log = AccessLog()
        self.last_training = None

    def should_show(self, path: str, attrs: Dict[str, Any]) -> bool:
        """Evaluate rules and log access for learning."""
        result = super().should_show(path, attrs)

        # Log access decision
        if self.enable_learning:
            self.access_log.record(path, attrs, shown=result, accessed=False)

        return result

    def on_file_accessed(self, path: str):
        """Called when file is actually opened/read (via FUSE)."""
        if self.enable_learning:
            self.access_log.mark_accessed(path)

    def should_retrain(self) -> bool:
        """Check if it's time to retrain the model."""
        if not self.last_training:
            return True

        return datetime.now() - self.last_training >= self.learning_interval

    async def learn_and_update_rules(self):
        """Train model and generate new rules from usage patterns."""
        if not self.should_retrain():
            return

        logger.info("Starting ML rule generation...")

        # Train model
        generator = MLRuleGenerator(self.access_log, model_type="decision_tree")
        success = generator.train(training_window_days=30)

        if not success:
            logger.warning("ML training failed")
            return

        # Generate rules
        learned_rules = generator.generate_rules(min_confidence=0.8)

        # Remove old learned rules
        self._remove_learned_rules()

        # Add new learned rules
        for rule in learned_rules:
            self.add_rule(rule)

        self.last_training = datetime.now()

        logger.info(f"Generated {len(learned_rules)} learned rules")

    def _remove_learned_rules(self):
        """Remove previously learned rules."""
        self._rules = [
            r for r in self._rules
            if not (r.metadata.get('source') == 'ml')
        ]
```

### Configuration

```yaml
shadowfs:
  rule_engine:
    enable_learning: true
    learning_interval: "7 days"
    min_confidence: 0.8
    max_learned_rules: 50

  learning:
    model_type: decision_tree  # or random_forest
    training_window: "30 days"
    features:
      - size
      - extension
      - mtime_age
      - directory_depth
      - access_frequency

    # Auto-retrain schedule
    retrain_schedule: "0 2 * * 0"  # 2am every Sunday
```

### Use Cases

1. **Auto-hide unused files**: "User never accesses .log files → hide them"
2. **Personalization**: Learn user's file preferences over time
3. **Workspace optimization**: Hide directories rarely visited
4. **Anomaly detection**: Flag unusual files (different from normal patterns)
5. **Smart defaults**: Generate initial rules from usage data

### Implementation Complexity

**Very High** - Requires:
- ML library integration (scikit-learn)
- Feature engineering from file attributes
- Training pipeline and model persistence
- Decision tree to rule conversion
- Access logging infrastructure
- Performance (model inference overhead)
- Validation (avoid false positives)

### Integration

- New `ml/` package in Integration layer
- Access logging via FUSE layer
- Periodic background training job
- Model versioning and A/B testing
- Metrics for rule accuracy (precision/recall)
- User feedback mechanism

---

## 8. Rule Template and Inheritance System

### The Pattern

Define reusable rule templates with parameterization, enabling DRY configuration and rapid rule creation.

### How It Works

```python
@dataclass
class RuleTemplate:
    """Template for creating rule families."""

    template_id: str
    description: str
    base_rule: Rule
    parameters: Dict[str, Any] = field(default_factory=dict)
    parameter_schema: Dict[str, Any] = field(default_factory=dict)


class TemplateRuleEngine(RuleEngine):
    """Rule engine with template support."""

    def __init__(self):
        super().__init__()
        self.templates: Dict[str, RuleTemplate] = {}
        self._register_builtin_templates()

    def _register_builtin_templates(self):
        """Register built-in rule templates."""
        # Hide by extension
        self.register_template(
            template_id="hide_by_extension",
            description="Hide all files with given extension",
            base_rule=Rule(
                action=RuleAction.EXCLUDE,
                patterns=["**/*.{{extension}}"]
            ),
            parameters={"extension": "txt"},
            parameter_schema={
                "extension": {"type": "string", "required": True}
            }
        )

        # Hide old files
        self.register_template(
            template_id="hide_old_files",
            description="Hide files older than specified days",
            base_rule=Rule(
                action=RuleAction.EXCLUDE,
                patterns=["{{path_pattern}}"],
                conditions=[
                    Condition(
                        field="mtime",
                        operator="lt",
                        value="{{days_old}} days ago"
                    )
                ]
            ),
            parameters={
                "path_pattern": "**/*",
                "days_old": 30
            },
            parameter_schema={
                "path_pattern": {"type": "string", "required": True},
                "days_old": {"type": "integer", "required": True, "min": 1}
            }
        )

    def register_template(
        self,
        template_id: str,
        description: str,
        base_rule: Rule,
        parameters: Dict[str, Any],
        parameter_schema: Dict[str, Any]
    ):
        """Register a reusable rule template."""
        self.templates[template_id] = RuleTemplate(
            template_id=template_id,
            description=description,
            base_rule=base_rule,
            parameters=parameters,
            parameter_schema=parameter_schema
        )

    def instantiate_template(
        self,
        template_id: str,
        overrides: Dict[str, Any],
        name: Optional[str] = None
    ) -> Rule:
        """Create rule instance from template.

        Args:
            template_id: Template to instantiate
            overrides: Parameter values to override defaults
            name: Optional name for the rule

        Returns:
            Instantiated Rule object
        """
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Merge parameters
        params = {**template.parameters, **overrides}

        # Validate parameters
        self._validate_params(params, template.parameter_schema)

        # Deep copy base rule
        rule = copy.deepcopy(template.base_rule)

        # Substitute parameters
        rule = self._substitute_params(rule, params)

        # Set name
        if name:
            rule.name = name
        else:
            rule.name = f"{template_id}_{hash(frozenset(params.items()))}"

        return rule

    def _validate_params(self, params: Dict[str, Any], schema: Dict[str, Any]):
        """Validate parameters against schema."""
        for param_name, param_schema in schema.items():
            # Required check
            if param_schema.get("required") and param_name not in params:
                raise ValueError(f"Required parameter {param_name} missing")

            if param_name not in params:
                continue

            value = params[param_name]

            # Type check
            expected_type = param_schema.get("type")
            if expected_type == "string" and not isinstance(value, str):
                raise TypeError(f"Parameter {param_name} must be string")
            elif expected_type == "integer" and not isinstance(value, int):
                raise TypeError(f"Parameter {param_name} must be integer")

            # Range check
            if "min" in param_schema and value < param_schema["min"]:
                raise ValueError(f"Parameter {param_name} below minimum")
            if "max" in param_schema and value > param_schema["max"]:
                raise ValueError(f"Parameter {param_name} above maximum")

    def _substitute_params(self, rule: Rule, params: Dict[str, Any]) -> Rule:
        """Replace {{param}} placeholders in rule."""
        import re

        # Substitute in patterns
        rule.patterns = [
            self._substitute_string(p, params)
            for p in rule.patterns
        ]

        # Substitute in condition values
        for condition in rule.conditions:
            if isinstance(condition.value, str):
                condition.value = self._substitute_string(condition.value, params)

        return rule

    def _substitute_string(self, text: str, params: Dict[str, Any]) -> str:
        """Replace {{key}} with params[key]."""
        import re

        def replacer(match):
            key = match.group(1)
            if key in params:
                return str(params[key])
            else:
                raise ValueError(f"Parameter {key} not provided")

        return re.sub(r'\{\{(\w+)\}\}', replacer, text)

    def load_template_instances(self, config: List[Dict]) -> List[Rule]:
        """Load rule instances from template configuration."""
        rules = []

        for item in config:
            template_id = item.get("template")
            if not template_id:
                continue

            params = item.get("params", {})
            name = item.get("name")

            rule = self.instantiate_template(template_id, params, name)
            rules.append(rule)

        return rules
```

### Configuration

```yaml
# Define templates (can be in separate library file)
rule_templates:
  hide_by_extension:
    description: "Hide all files with given extension"
    action: exclude
    patterns: ["**/*.{{extension}}"]
    parameters:
      extension:
        type: string
        required: true

  hide_old_files:
    description: "Hide files older than specified days"
    action: exclude
    patterns: ["{{path_pattern}}"]
    conditions:
      - field: mtime
        operator: lt
        value: "{{days_old}} days ago"
    parameters:
      path_pattern:
        type: string
        default: "**/*"
      days_old:
        type: integer
        default: 30
        min: 1

  hide_large_in_path:
    description: "Hide large files in specific path"
    action: exclude
    patterns: ["{{path}}/**"]
    conditions:
      - field: size
        operator: gt
        value: "{{size_mb}}"
    parameters:
      path:
        type: string
        required: true
      size_mb:
        type: integer
        default: 100

rules:
  # Instantiate templates
  - template: hide_by_extension
    params:
      extension: pyc
    name: "hide_python_cache"

  - template: hide_by_extension
    params:
      extension: bak

  - template: hide_by_extension
    params:
      extension: tmp

  - template: hide_old_files
    params:
      path_pattern: "**/logs/**"
      days_old: 7
    name: "cleanup_old_logs"

  - template: hide_old_files
    params:
      path_pattern: "**/tmp/**"
      days_old: 1

  - template: hide_large_in_path
    params:
      path: "**/videos"
      size_mb: 500
```

### Use Cases

1. **Rule families**: "Hide by extension" → .pyc, .bak, .tmp, .o
2. **DRY configuration**: Define once, instantiate many times
3. **Organizational standards**: Share templates across teams
4. **Rapid prototyping**: Quickly create similar rules
5. **Consistency**: All similar rules follow same pattern
6. **Maintainability**: Update template → all instances update

### Implementation Complexity

**Medium** - Requires:
- Template parsing and substitution
- Parameter validation
- Schema definition language
- Template registry
- Documentation generation

### Integration

- Enhanced config schema for templates
- Template library (built-in + custom)
- CLI: `shadowfs-ctl template list`
- Documentation: auto-generate from templates
- Import/export template libraries

---

## 9. Rule Execution Tracing and Debugging

### The Pattern

Provide detailed logging, explanation, and visualization of rule evaluation to answer "Why is this file hidden?"

### How It Works

```python
@dataclass
class RuleEvaluation:
    """Record of a single rule evaluation."""

    path: str
    rule: Rule
    matched: bool
    reason: str
    timestamp: datetime
    duration_ms: float
    pattern_results: Dict[str, bool]
    condition_results: Dict[str, bool]


@dataclass
class RuleTrace:
    """Complete trace of rule evaluation for a path."""

    path: str
    evaluations: List[RuleEvaluation]
    final_decision: Optional[bool]
    winning_rule: Optional[Rule]
    total_duration_ms: float

    def explain(self) -> str:
        """Generate human-readable explanation."""
        lines = []
        lines.append(f"Rule Evaluation for: {self.path}")
        lines.append("=" * 60)
        lines.append(f"Final Decision: {'✓ SHOW' if self.final_decision else '✗ HIDE'}")
        lines.append(f"Total Duration: {self.total_duration_ms:.2f}ms")
        lines.append("")

        if self.winning_rule:
            lines.append(f"Winning Rule: {self.winning_rule.name}")
            lines.append(f"Action: {self.winning_rule.action.value}")
            lines.append("")

        lines.append("Rule Evaluation Sequence:")
        lines.append("-" * 60)

        for i, eval in enumerate(self.evaluations, 1):
            status = "✓ MATCHED" if eval.matched else "✗ NO MATCH"
            lines.append(f"{i}. {eval.rule.name or 'unnamed'}: {status}")
            lines.append(f"   Reason: {eval.reason}")
            lines.append(f"   Duration: {eval.duration_ms:.2f}ms")

            if eval.pattern_results:
                lines.append(f"   Pattern Results:")
                for pattern, result in eval.pattern_results.items():
                    symbol = "✓" if result else "✗"
                    lines.append(f"     {symbol} {pattern}")

            if eval.condition_results:
                lines.append(f"   Condition Results:")
                for cond, result in eval.condition_results.items():
                    symbol = "✓" if result else "✗"
                    lines.append(f"     {symbol} {cond}")

            lines.append("")

        return "\n".join(lines)


class TracingRuleEngine(RuleEngine):
    """Rule engine with detailed execution tracing."""

    def __init__(self, enable_tracing: bool = False, max_traces: int = 1000):
        super().__init__()
        self.enable_tracing = enable_tracing
        self.trace_log: Deque[RuleTrace] = deque(maxlen=max_traces)

    def should_show(self, path: str, attrs: Dict[str, Any]) -> bool:
        """Evaluate with optional tracing."""
        if not self.enable_tracing:
            return super().should_show(path, attrs)

        # Tracing enabled
        start_time = time.time()
        trace = RuleTrace(
            path=path,
            evaluations=[],
            final_decision=None,
            winning_rule=None,
            total_duration_ms=0.0
        )

        for rule in self._rules:
            if not rule.enabled:
                continue

            eval_start = time.time()

            # Detailed evaluation with tracing
            matched, reason, pattern_results, condition_results = self._evaluate_rule_detailed(
                rule, path, attrs
            )

            eval_duration = (time.time() - eval_start) * 1000

            trace.evaluations.append(RuleEvaluation(
                path=path,
                rule=rule,
                matched=matched,
                reason=reason,
                timestamp=datetime.now(),
                duration_ms=eval_duration,
                pattern_results=pattern_results,
                condition_results=condition_results
            ))

            if matched:
                trace.final_decision = (rule.action == RuleAction.INCLUDE)
                trace.winning_rule = rule
                break

        else:
            # No rules matched - use default
            trace.final_decision = (self._default_action == RuleAction.INCLUDE)
            trace.evaluations.append(RuleEvaluation(
                path=path,
                rule=None,
                matched=False,
                reason=f"No rules matched, using default: {self._default_action.value}",
                timestamp=datetime.now(),
                duration_ms=0.0,
                pattern_results={},
                condition_results={}
            ))

        trace.total_duration_ms = (time.time() - start_time) * 1000
        self.trace_log.append(trace)

        return trace.final_decision

    def _evaluate_rule_detailed(
        self, rule: Rule, path: str, attrs: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, bool], Dict[str, bool]]:
        """Evaluate rule with detailed results for tracing."""
        pattern_results = {}
        condition_results = {}

        # Evaluate patterns
        pattern_matched = False
        for pattern in rule.patterns:
            result = self._pattern_matcher.match(pattern, path)
            pattern_results[pattern] = result
            if result:
                pattern_matched = True

        if not pattern_matched:
            return False, "No patterns matched", pattern_results, condition_results

        # Evaluate conditions
        for condition in rule.conditions:
            result = self._evaluate_condition(condition, attrs)
            cond_str = f"{condition.field} {condition.operator} {condition.value}"
            condition_results[cond_str] = result

        # Combine conditions
        if rule.condition_operator == RuleOperator.AND:
            cond_matched = all(condition_results.values())
        else:  # OR
            cond_matched = any(condition_results.values()) if condition_results else True

        if not cond_matched:
            return False, "Conditions not satisfied", pattern_results, condition_results

        return True, "All criteria matched", pattern_results, condition_results

    def get_trace(self, path: str) -> Optional[RuleTrace]:
        """Get most recent trace for specific path."""
        for trace in reversed(self.trace_log):
            if trace.path == path:
                return trace
        return None

    def explain(self, path: str) -> str:
        """Explain why a file is shown/hidden."""
        trace = self.get_trace(path)
        if trace:
            return trace.explain()
        return f"No trace found for: {path}"

    def get_trace_statistics(self) -> Dict[str, Any]:
        """Get statistics from trace log."""
        if not self.trace_log:
            return {}

        total_traces = len(self.trace_log)
        total_duration = sum(t.total_duration_ms for t in self.trace_log)
        avg_duration = total_duration / total_traces

        # Count by decision
        shown = sum(1 for t in self.trace_log if t.final_decision)
        hidden = total_traces - shown

        # Average evaluations per trace
        total_evals = sum(len(t.evaluations) for t in self.trace_log)
        avg_evals = total_evals / total_traces

        return {
            "total_traces": total_traces,
            "avg_duration_ms": avg_duration,
            "shown": shown,
            "hidden": hidden,
            "avg_evaluations_per_trace": avg_evals,
        }
```

### CLI Integration

```bash
# Explain why file is hidden
$ shadowfs-ctl explain /mnt/shadowfs/project/file.pyc

Rule Evaluation for: project/file.pyc
============================================================
Final Decision: ✗ HIDE
Total Duration: 0.15ms

Winning Rule: hide_build_artifacts
Action: exclude

Rule Evaluation Sequence:
------------------------------------------------------------
1. hide_build_artifacts: ✓ MATCHED
   Reason: All criteria matched
   Duration: 0.12ms
   Pattern Results:
     ✓ **/*.pyc
   Condition Results:
     (no conditions)

# Get trace statistics
$ shadowfs-ctl trace-stats

Trace Statistics:
- Total traces: 1,234
- Average duration: 0.18ms
- Files shown: 892 (72.3%)
- Files hidden: 342 (27.7%)
- Avg evaluations per file: 2.1
```

### Use Cases

1. **Debugging**: "Why is this file hidden?"
2. **Configuration testing**: Verify rules work as intended
3. **Performance profiling**: Identify slow rules
4. **Audit trails**: Track rule decisions over time
5. **Rule optimization**: Find redundant or never-matching rules
6. **User education**: Help users understand rule behavior

### Implementation Complexity

**Medium** - Requires:
- Detailed evaluation tracking
- Performance overhead management
- Storage for traces (in-memory LRU)
- Pretty-printing and formatting
- CLI/API integration

### Integration

- Control server API: `GET /explain?path=/foo/bar`
- Web UI: Interactive trace viewer
- Logging integration
- Metrics: rule match rates, evaluation times
- Export traces to JSON for analysis

---

## 10. Rule Performance Optimizer

### The Pattern

Automatically optimize rule evaluation order and create indexes for maximum performance.

### How It Works

```python
@dataclass
class RuleStats:
    """Performance statistics for a rule."""

    rule: Rule
    evaluations: int = 0
    matches: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    selectivity: float = 0.0  # matches / evaluations


class OptimizingRuleEngine(RuleEngine):
    """Rule engine with automatic performance optimization."""

    def __init__(
        self,
        auto_optimize: bool = True,
        optimization_interval: int = 1000,
        optimization_strategy: str = "hybrid"
    ):
        super().__init__()
        self.auto_optimize = auto_optimize
        self.optimization_interval = optimization_interval
        self.optimization_strategy = optimization_strategy
        self.evaluation_count = 0
        self.stats: Dict[str, RuleStats] = {}

    def should_show(self, path: str, attrs: Dict[str, Any]) -> bool:
        """Evaluate with statistics tracking."""
        result = super().should_show(path, attrs)

        self.evaluation_count += 1

        # Periodically optimize
        if (self.auto_optimize and
            self.evaluation_count % self.optimization_interval == 0):
            self._optimize_rules()

        return result

    def _evaluate_rule(self, rule: Rule, path: str, attrs: Dict[str, Any]) -> bool:
        """Evaluate with performance tracking."""
        rule_id = rule.name or id(rule)

        # Initialize stats if needed
        if rule_id not in self.stats:
            self.stats[rule_id] = RuleStats(rule=rule)

        stats = self.stats[rule_id]

        # Time evaluation
        start = time.time()
        matched = super()._evaluate_rule(rule, path, attrs)
        duration = (time.time() - start) * 1000

        # Update statistics
        stats.evaluations += 1
        if matched:
            stats.matches += 1

        stats.total_duration_ms += duration
        stats.avg_duration_ms = stats.total_duration_ms / stats.evaluations
        stats.selectivity = stats.matches / stats.evaluations

        return matched

    def _optimize_rules(self):
        """Reorder rules for optimal performance."""
        if self.optimization_strategy == "selectivity":
            self._optimize_by_selectivity()
        elif self.optimization_strategy == "performance":
            self._optimize_by_performance()
        elif self.optimization_strategy == "hybrid":
            self._optimize_hybrid()

        logger.info(f"Optimized rules after {self.evaluation_count} evaluations")

    def _optimize_by_selectivity(self):
        """Order rules by selectivity (high selectivity first)."""
        scored_rules = []

        for rule in self._rules:
            rule_id = rule.name or id(rule)
            stats = self.stats.get(rule_id)

            if stats:
                score = stats.selectivity
            else:
                score = rule.priority / 1000  # Use priority as fallback

            scored_rules.append((score, rule))

        # Sort by score (descending)
        scored_rules.sort(key=lambda x: x[0], reverse=True)
        self._rules = [rule for _, rule in scored_rules]

    def _optimize_by_performance(self):
        """Order rules by performance (fast rules first)."""
        scored_rules = []

        for rule in self._rules:
            rule_id = rule.name or id(rule)
            stats = self.stats.get(rule_id)

            if stats:
                # Lower duration = higher score
                score = 1000 / max(stats.avg_duration_ms, 0.01)
            else:
                score = rule.priority / 1000

            scored_rules.append((score, rule))

        scored_rules.sort(key=lambda x: x[0], reverse=True)
        self._rules = [rule for _, rule in scored_rules]

    def _optimize_hybrid(self):
        """Optimize by both selectivity and performance.

        Score = selectivity / duration
        (High selectivity + low duration = high score)
        """
        scored_rules = []

        for rule in self._rules:
            rule_id = rule.name or id(rule)
            stats = self.stats.get(rule_id)

            if stats:
                # Hybrid score: selectivity / duration
                score = stats.selectivity / max(stats.avg_duration_ms, 0.01)
            else:
                score = rule.priority / 1000

            scored_rules.append((score, rule))

        scored_rules.sort(key=lambda x: x[0], reverse=True)
        self._rules = [rule for _, rule in scored_rules]

    def get_rule_stats(self) -> List[RuleStats]:
        """Get performance statistics for all rules."""
        return list(self.stats.values())

    def get_optimization_report(self) -> Dict[str, Any]:
        """Generate optimization report."""
        stats_list = self.get_rule_stats()

        if not stats_list:
            return {}

        # Sort by various metrics
        by_selectivity = sorted(stats_list, key=lambda s: s.selectivity, reverse=True)
        by_duration = sorted(stats_list, key=lambda s: s.avg_duration_ms)
        by_evaluations = sorted(stats_list, key=lambda s: s.evaluations, reverse=True)

        return {
            "total_evaluations": self.evaluation_count,
            "total_rules": len(stats_list),
            "most_selective": [
                {"rule": s.rule.name, "selectivity": s.selectivity}
                for s in by_selectivity[:5]
            ],
            "fastest_rules": [
                {"rule": s.rule.name, "avg_duration_ms": s.avg_duration_ms}
                for s in by_duration[:5]
            ],
            "most_evaluated": [
                {"rule": s.rule.name, "evaluations": s.evaluations}
                for s in by_evaluations[:5]
            ],
            "optimization_strategy": self.optimization_strategy,
        }
```

### Configuration

```yaml
shadowfs:
  rule_engine:
    auto_optimize: true
    optimization_interval: 1000  # Reoptimize every 1000 evaluations
    optimization_strategy: hybrid  # selectivity, performance, or hybrid

    # Advanced: Manual performance hints
    rule_hints:
      hide_pyc_files:
        estimated_selectivity: 0.8
        estimated_duration_ms: 0.1
```

### Use Cases

1. **Large rule sets**: 100+ rules slow without optimization
2. **Production performance**: Minimize evaluation overhead
3. **Adaptive systems**: Rules that change effectiveness over time
4. **Performance debugging**: Identify slow rules
5. **Resource optimization**: Reduce CPU usage

### Implementation Complexity

**High** - Requires:
- Statistics collection infrastructure
- Multiple optimization algorithms
- Balance optimization cost vs. benefit
- Preserve user priorities vs. auto-optimization
- Performance monitoring

### Integration

- Metrics export for rule performance
- Control API: `GET /rules/stats`
- Periodic optimization jobs
- Optional: ML-based optimization prediction

---

## Implementation Priority and Roadmap

### Complexity and Impact Matrix

| Extension | Complexity | Impact | Priority | Effort |
|-----------|-----------|--------|----------|--------|
| 1. Dynamic Modification | Medium | High | **P0** | 2 weeks |
| 4. Conflict Resolution | Medium | High | **P0** | 2 weeks |
| 9. Execution Tracing | Medium | High | **P0** | 2 weeks |
| 2. Temporal Scheduler | Medium-High | Medium | **P1** | 3 weeks |
| 3. Context-Aware | High | High | **P1** | 4 weeks |
| 8. Rule Templates | Medium | Medium | **P1** | 2 weeks |
| 5. Rule Chains | Medium-High | Medium | **P2** | 3 weeks |
| 10. Performance Optimizer | High | Medium | **P2** | 4 weeks |
| 6. External Data | High | Medium | **P2** | 5 weeks |
| 7. ML Generator | Very High | Low | **P3** | 8+ weeks |

### Phased Implementation

#### Phase 7a: Foundation Extensions (Weeks 13-15)
**Critical for production use**

- ✅ Extension #1: Dynamic Rule Modification
  - Hot-reload without remount
  - A/B testing support
  - Config file watching

- ✅ Extension #4: Conflict Resolution
  - Detect overlapping rules
  - Multiple resolution strategies
  - Conflict logging

- ✅ Extension #9: Execution Tracing
  - "Why is this hidden?" explanations
  - Performance profiling
  - CLI integration

**Deliverables**: Production-ready debugging and runtime modification

---

#### Phase 7b: Advanced Features (Weeks 16-19)
**Enhanced functionality**

- ✅ Extension #2: Temporal Scheduler
  - Cron-like scheduling
  - Time validity windows
  - Dynamic expressions

- ✅ Extension #8: Rule Templates
  - Parameterized templates
  - Built-in template library
  - Template validation

- ✅ Extension #3: Context-Aware Rules
  - User/network/system awareness
  - Context providers
  - Multi-tenant support

**Deliverables**: Smart, adaptive rule system

---

#### Phase 7c: Integration & Optimization (Weeks 20-24)
**Performance and extensibility**

- ✅ Extension #5: Rule Chains
  - Composite rules
  - Dependency management
  - Cycle detection

- ✅ Extension #10: Performance Optimizer
  - Auto-optimize rule order
  - Statistics tracking
  - Multiple strategies

- ✅ Extension #6: External Data Integration
  - Git metadata
  - API queries
  - Database lookups

**Deliverables**: High-performance, extensible rule engine

---

#### Phase 7d: Experimental (Weeks 25+)
**Research and innovation**

- ✅ Extension #7: ML Rule Generator
  - Learn from access patterns
  - Auto-generate rules
  - Adaptive filtering

**Deliverables**: Intelligent, self-optimizing system

---

## Integration with ShadowFS Architecture

### Layer Integration

**Layer 1 (Foundation)**:
- No changes needed - extensions build on existing primitives

**Layer 2 (Infrastructure)**:
- **Config Manager**: Extended schemas for new rule types
- **Cache Manager**: Cache external data, context, ML model results
- **Metrics**: New metrics for rule performance, conflicts, ML accuracy
- **Logger**: Enhanced with tracing and debugging output

**Layer 3 (Integration)**:
- **RuleEngine**: Core location for all extension implementations
- **PatternMatcher**: Enhanced for specificity calculation
- New components:
  - `context_provider.py` (Extension #3)
  - `data_sources/` package (Extension #6)
  - `ml/` package (Extension #7)
  - `rule_templates.py` (Extension #8)
  - `rule_optimizer.py` (Extension #10)

**Layer 4 (Application)**:
- **Control Server**: New API endpoints
  - `POST /rules/reload` (hot-reload)
  - `GET /rules/conflicts` (conflict report)
  - `GET /explain?path=/foo` (trace explanation)
  - `GET /rules/stats` (performance statistics)
  - `POST /rules/optimize` (trigger optimization)
- **CLI**: New commands
  - `shadowfs-ctl reload`
  - `shadowfs-ctl explain <path>`
  - `shadowfs-ctl conflicts`
  - `shadowfs-ctl optimize`

---

## Advanced Configuration Example

```yaml
shadowfs:
  version: "2.0"

  rule_engine:
    # Extension #1: Dynamic modification
    hot_reload: true
    config_watch: true

    # Extension #4: Conflict resolution
    conflict_resolution: specificity
    log_conflicts: true
    conflict_threshold: 100

    # Extension #9: Tracing
    enable_tracing: false  # Enable on-demand
    trace_retention: 1000

    # Extension #10: Optimization
    auto_optimize: true
    optimization_interval: 5000
    optimization_strategy: hybrid

  # Extension #3: Context providers
  context:
    providers:
      - type: user
      - type: network
      - type: system_resources
      - type: git
        repo_path: /source
    cache_ttl: 10  # Cache context for 10 seconds

  # Extension #6: Data sources
  data_sources:
    git:
      type: git
      repo_path: /source
      cache_ttl: 600

    content_api:
      type: rest_api
      base_url: https://api.example.com
      auth_token: ${API_TOKEN}

  # Extension #7: Machine learning
  learning:
    enabled: true
    model_type: decision_tree
    training_window_days: 30
    min_confidence: 0.8
    retrain_schedule: "0 2 * * 0"  # 2am Sundays

  # Extension #8: Rule templates
  rule_templates:
    hide_by_extension:
      action: exclude
      patterns: ["**/*.{{ext}}"]

    hide_old_in_path:
      action: exclude
      patterns: ["{{path}}/**"]
      conditions:
        - field: mtime
          operator: lt
          value: "{{days}} days ago"

rules:
  # Extension #2: Temporal rules
  - name: "Work hours only"
    action: exclude
    patterns: ["*/personal/**"]
    schedule: "0 0-8,18-23 * * *"
    timezone: "America/New_York"

  # Extension #3: Context-aware
  - name: "Corporate network restrictions"
    action: exclude
    patterns: ["*/private/**"]
    context:
      network: corporate

  # Extension #5: Composite rule
  - name: "Large old media"
    action: exclude
    type: composite
    operator: and
    subrules:
      - is_large_file
      - is_old_file
      - is_media_file

  # Extension #6: External data
  - name: "Hide by git author"
    action: exclude
    patterns: ["**/*"]
    conditions:
      - field: git_author
        operator: eq
        value: "deprecated@example.com"
        source_type: git

  # Extension #8: Template instance
  - template: hide_by_extension
    params:
      ext: pyc
    name: "hide_python_cache"
```

---

## Summary

The current RuleEngine provides a **solid foundation** with pattern matching, conditions, and priority-based evaluation. The **10 extension patterns** documented here would transform it into a **comprehensive, intelligent decision engine** rivaling enterprise rule systems.

**Key Capabilities Unlocked**:
- ✅ **Temporal awareness**: Schedule-based and time-limited rules
- ✅ **Context sensitivity**: User, network, system state adaptation
- ✅ **Intelligence**: Machine learning from usage patterns
- ✅ **Composability**: Build complex rules from simple components
- ✅ **Extensibility**: Query external systems (Git, APIs, databases)
- ✅ **Debuggability**: Explain every decision with detailed traces
- ✅ **Performance**: Auto-optimize for maximum speed
- ✅ **Maintainability**: Templates and DRY principles
- ✅ **Reliability**: Conflict detection and resolution
- ✅ **Flexibility**: Hot-reload without downtime

These extensions follow proven patterns from enterprise rule engines (Drools, business rules management systems) and adapt them for filesystem filtering, creating a unique and powerful capability for ShadowFS.

---

**References**:
- [architecture.md](architecture.md) - Core ShadowFS architecture
- [middleware-ideas.md](middleware-ideas.md) - Middleware extension patterns
- [virtual-layers.md](virtual-layers.md) - Virtual organizational layers
- [CLAUDE.md](../CLAUDE.md) - Project overview
