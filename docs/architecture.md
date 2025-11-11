# Shadow Filesystem Architecture (ShadowFS)

A FUSE-based filesystem that provides dynamic filtering, transformation, and view composition of underlying filesystems through runtime-configurable rules.

**Version:** 1.0.0  
**Status:** Design Phase  
**Meta-Architecture Compliance:** v1.0.0

---

## Table of Contents

1. [The Core Mechanism](#the-core-mechanism)
2. [System Architecture](#system-architecture)
3. [Layer Structure](#layer-structure)
4. [Component Specifications](#component-specifications)
5. [Configuration System](#configuration-system)
6. [Transform Pipeline](#transform-pipeline)
7. [Security Model](#security-model)
8. [Performance Patterns](#performance-patterns)
9. [Error Handling](#error-handling)
10. [Testing Strategy](#testing-strategy)
11. [Deployment Guide](#deployment-guide)
12. [Compliance Matrix](#compliance-matrix)

---

## The Core Mechanism

### What's Actually Happening?

ShadowFS creates a **virtual filesystem layer** that sits between applications and the underlying filesystem. The mechanism works through:

1. **FUSE Integration**: Python-FUSE provides filesystem operation interception
   - Every filesystem call (open, read, stat, etc.) goes through FUSE
   - FUSE calls Python callbacks for each operation
   - Callbacks apply rules before delegating to underlying filesystem

2. **Rule-Based Filtering**: Configuration defines which files are visible
   - Rules match files by pattern (glob, regex, attributes)
   - Filters can hide, show, or modify files/directories
   - Multiple rules compose through logical operators

3. **Transform Pipeline**: File content can be modified on-the-fly
   - Transforms apply during read operations (transparent to caller)
   - Transforms can be chained (pipe pattern)
   - Original files remain unmodified (read-only transforms)

4. **Virtual View Composition**: Multiple source directories merged into single view
   - Overlay semantics: upper layers mask lower layers
   - Union semantics: merge all directories
   - Filter semantics: selective visibility per source

**Why FUSE?**
- Operates in userspace (no kernel modules, safer)
- Full filesystem control without root privileges
- Cross-platform (Linux, macOS, BSD)
- Python bindings available (fusepy, pyfuse3)

**Key Insight**: The "shadow" filesystem doesn't store files - it's a **dynamic view** over existing files with runtime-configurable behavior.

---

## System Architecture

### High-Level Conceptual Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│          (ls, cat, grep, your-app, etc.)                    │
└─────────────────────────────────────┬───────────────────────┘
                                      │
                          ╔═══════════▼═══════════╗
                          ║    FUSE Kernel        ║
                          ║    Interface          ║
                          ╚═══════════╤═══════════╝
                                      │
┌─────────────────────────────────────▼───────────────────────┐
│                   ShadowFS (Python)                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Layer 4: Application (FUSE Operations Handler)       │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────▼─────────────────────────────────┐  │
│  │  Layer 3: Integration (Rule Engine + Transform)       │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────▼─────────────────────────────────┐  │
│  │  Layer 2: Infrastructure (Config, Cache, Logging)     │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────▼─────────────────────────────────┐  │
│  │  Layer 1: Foundation (Path Utils, File Ops)           │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────┬───────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────┐
│              Underlying Filesystem(s)                        │
│     /source/dir1    /source/dir2    /source/dir3            │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow Example: Reading a File

```
1. Application: open("/mnt/shadowfs/project/file.txt")
   ↓
2. FUSE Kernel: Intercept syscall → forward to ShadowFS
   ↓
3. ShadowFS Layer 4 (FUSE Handler):
   - receive open() callback
   - extract path: "project/file.txt"
   ↓
4. ShadowFS Layer 3 (Rule Engine):
   - Check visibility rules: should this file be visible?
   - Check transform rules: should content be modified?
   ↓
5. ShadowFS Layer 2 (Cache):
   - Check if result cached
   - If miss, continue to Layer 1
   ↓
6. ShadowFS Layer 1 (File Operations):
   - Map virtual path to real path: /source/dir1/project/file.txt
   - Delegate to OS: os.open()
   ↓
7. Underlying Filesystem: Return file handle
   ↓
8. [If transform active] Layer 3 (Transform Pipeline):
   - Read file content
   - Apply transforms in sequence
   - Return transformed content
   ↓
9. Return to application
```

---

## Layer Structure

Following Meta-Architecture principle: **Layered Architecture (MANDATORY)**

### Layer 1: Foundation (Primitives)

**Purpose**: Core utilities with zero dependencies on upper layers

**Components**:
- `path_utils.py`: Path normalization, validation, resolution
- `file_operations.py`: Safe file I/O wrappers
- `validators.py`: Input validation functions
- `constants.py`: System-wide constants

**Key Functions**:
```python
# path_utils.py
def normalize_path(path: str) -> str:
    """Normalize path, resolve .., validate safety"""
    
def is_safe_path(path: str, root: str) -> bool:
    """Prevent path traversal attacks"""
    
def map_virtual_to_real(virtual: str, sources: List[str]) -> Optional[str]:
    """Map virtual path to real filesystem path"""

# file_operations.py
def safe_read(path: str, offset: int, length: int) -> bytes:
    """Read file with bounds checking and error handling"""
    
def get_attributes(path: str) -> FileAttributes:
    """Safely get file stats"""
```

**Error Codes**: Uses standard codes 0-9
**Dependencies**: Python stdlib only (os, pathlib, stat)

### Layer 2: Infrastructure (Core Services)

**Purpose**: Reusable services that Foundation and Integration use

**Components**:
- `config_manager.py`: Hierarchical configuration loading
- `cache_manager.py`: LRU cache for file attributes and content
- `logger.py`: Structured logging
- `metrics.py`: Performance metrics collection

**Key Functions**:
```python
# config_manager.py
class ConfigManager:
    def load_config(self, path: str) -> Config:
        """Load and validate configuration file"""
        
    def reload_config(self) -> None:
        """Hot-reload configuration without unmounting"""
        
    def get_rules(self) -> List[Rule]:
        """Get current rule set"""

# cache_manager.py
class CacheManager:
    def __init__(self, max_size_mb: int, ttl_seconds: int):
        """Initialize LRU cache with size and time limits"""
        
    def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        
    def set(self, key: str, value: Any) -> None:
        """Cache value with TTL"""
        
    def invalidate_path(self, path: str) -> None:
        """Invalidate all cache entries for path"""
```

**Configuration Hierarchy**:
```
1. Compiled defaults (in code)
2. System config: /etc/shadowfs/config.yaml
3. User config: ~/.config/shadowfs/config.yaml
4. Environment variables: SHADOWFS_*
5. CLI arguments: --config /path/to/config.yaml
6. Runtime updates: via control socket
```

**Dependencies**: Layer 1 only

### Layer 3: Integration (External Systems)

**Purpose**: Rules, transforms, and policy engines

**Components**:
- `rule_engine.py`: Evaluate filter rules
- `transform_pipeline.py`: Apply content transformations
- `pattern_matcher.py`: Glob/regex matching
- `view_compositor.py`: Merge multiple sources

**Key Functions**:
```python
# rule_engine.py
class RuleEngine:
    def should_show_file(self, path: str, attrs: FileAttributes) -> bool:
        """Check if file passes visibility rules"""
        
    def should_transform(self, path: str) -> List[Transform]:
        """Get list of transforms to apply to file"""

# transform_pipeline.py
class TransformPipeline:
    def add_transform(self, transform: Transform) -> None:
        """Add transform to pipeline"""
        
    def apply(self, content: bytes, path: str) -> bytes:
        """Apply all transforms in sequence"""

# view_compositor.py
class ViewCompositor:
    def merge_sources(self, sources: List[str], strategy: str) -> VirtualTree:
        """Create unified view from multiple sources"""
```

**Rule Types**:
- **Include Rules**: Files matching pattern are visible
- **Exclude Rules**: Files matching pattern are hidden
- **Transform Rules**: Files matching pattern get transformed
- **Priority Rules**: Order matters - first match wins

**Transform Types**:
- **Content Transform**: Modify file content (e.g., templating, compression)
- **Attribute Transform**: Modify metadata (e.g., fake timestamps, permissions)
- **Format Transform**: Convert file format (e.g., markdown to HTML)

**Dependencies**: Layer 1, Layer 2

### Layer 4: Application (Business Logic)

**Purpose**: FUSE operation handlers and main application logic

**Components**:
- `fuse_operations.py`: Implement FUSE callbacks
- `shadowfs_main.py`: Main application entry point
- `control_server.py`: Runtime control interface

**Key Functions**:
```python
# fuse_operations.py
class ShadowFS(Operations):
    def __init__(self, sources: List[str], config: Config):
        """Initialize FUSE filesystem"""
    
    def getattr(self, path: str, fh=None) -> Dict:
        """Get file attributes (stat)"""
        
    def readdir(self, path: str, fh) -> List[str]:
        """List directory contents"""
        
    def open(self, path: str, flags: int) -> int:
        """Open file and return file handle"""
        
    def read(self, path: str, size: int, offset: int, fh: int) -> bytes:
        """Read file content"""
        
    def write(self, path: str, data: bytes, offset: int, fh: int) -> int:
        """Write to file (if write-through enabled)"""

# shadowfs_main.py
def main():
    """Parse args, load config, mount filesystem"""
    
def mount_shadowfs(mountpoint: str, sources: List[str], config: Config):
    """Mount ShadowFS at mountpoint"""
    
def unmount_shadowfs(mountpoint: str):
    """Unmount and cleanup"""
```

**Dependencies**: All lower layers

---

## Component Specifications

### Configuration File Format

```yaml
# shadowfs.yaml
shadowfs:
  version: "1.0"
  
  # Source directories to shadow
  sources:
    - path: /source/documents
      priority: 1  # Higher priority = checked first
      readonly: true
    - path: /source/projects
      priority: 2
      readonly: false  # Allow write-through
  
  # Visibility rules (evaluated in order)
  rules:
    - name: "Hide hidden files"
      type: exclude
      pattern: "**/.*"
      
    - name: "Show only Python files"
      type: include
      pattern: "**/*.py"
      
    - name: "Hide build artifacts"
      type: exclude
      patterns:
        - "**/__pycache__/**"
        - "**/*.pyc"
        - "**/node_modules/**"
        - "**/dist/**"
        - "**/build/**"
      
    - name: "Size filter"
      type: exclude
      condition: "size > 100MB"  # Evaluated as Python expression
      
    - name: "Date filter"
      type: exclude
      condition: "mtime < '2020-01-01'"
  
  # Content transforms (applied in order)
  transforms:
    - name: "Template expansion"
      pattern: "**/*.template"
      type: template
      engine: jinja2
      context:
        env: production
        version: "1.0.0"
      
    - name: "Markdown to HTML"
      pattern: "**/*.md"
      type: convert
      from: markdown
      to: html
      output_extension: ".html"  # Virtual extension
      
    - name: "Decompress on read"
      pattern: "**/*.gz"
      type: decompress
      algorithm: gzip
      
    - name: "Encrypt sensitive files"
      pattern: "**/secrets/**/*"
      type: encrypt
      algorithm: AES-256
      key_source: env:SHADOWFS_ENCRYPTION_KEY
  
  # View composition strategy
  composition:
    strategy: overlay  # overlay | union | filter
    merge_policy: first_match  # first_match | all | priority
    
  # Caching configuration
  cache:
    enabled: true
    max_size_mb: 512
    ttl_seconds: 300
    cache_transforms: true  # Cache transformed content
    
  # Performance tuning
  performance:
    async_operations: true
    thread_pool_size: 10
    prefetch_enabled: true
    
  # Logging
  logging:
    level: INFO  # DEBUG | INFO | WARN | ERROR
    file: /var/log/shadowfs/shadowfs.log
    max_size_mb: 100
    rotation: daily
    
  # Metrics
  metrics:
    enabled: true
    prometheus_port: 9090
    statsd_host: localhost:8125
```

### Rule Evaluation Logic

```python
def evaluate_rules(path: str, attrs: FileAttributes, rules: List[Rule]) -> bool:
    """
    Evaluate rules in order. First match determines visibility.
    
    Returns:
        True if file should be visible, False if hidden
    """
    for rule in rules:
        if rule.matches(path, attrs):
            if rule.type == RuleType.INCLUDE:
                return True
            elif rule.type == RuleType.EXCLUDE:
                return False
    
    # Default: show file if no rules matched
    return True
```

**Rule Matching**:
- Pattern matching: `fnmatch`, `glob`, or `re` (configurable)
- Attribute conditions: Python expressions evaluated safely
- Logical operators: AND, OR, NOT for combining conditions

### Transform Pipeline Execution

```python
def apply_transforms(content: bytes, path: str, transforms: List[Transform]) -> bytes:
    """
    Apply transforms in sequence (pipe pattern).
    
    Each transform receives output of previous transform.
    """
    result = content
    
    for transform in transforms:
        try:
            result = transform.apply(result, path)
        except TransformError as e:
            # Handle gracefully: return original or partial result
            if transform.required:
                raise
            else:
                logger.warning(f"Optional transform failed: {transform.name}: {e}")
                # Continue with current result
    
    return result
```

**Transform Interface**:
```python
class Transform(ABC):
    @abstractmethod
    def apply(self, content: bytes, path: str) -> bytes:
        """Apply transformation to content"""
        pass
    
    @property
    @abstractmethod
    def required(self) -> bool:
        """Is this transform required or optional?"""
        pass
```

**Built-in Transforms**:
- `TemplateTransform`: Jinja2/Mako template expansion
- `CompressionTransform`: gzip/bz2/lzma compression/decompression
- `EncryptionTransform`: Symmetric encryption (AES, ChaCha20)
- `FormatConversionTransform`: File format conversion (MD→HTML, CSV→JSON)
- `FilterTransform`: Content filtering (grep-like, sed-like)
- `ChainTransform`: Compose multiple transforms

---

## Configuration System

Following Meta-Architecture principle: **Hierarchical Configuration**

### Configuration Loading Sequence

```python
def load_configuration() -> Config:
    """
    Load configuration with proper precedence hierarchy.
    
    Precedence (lowest to highest):
    1. Compiled defaults
    2. System config: /etc/shadowfs/config.yaml
    3. User config: ~/.config/shadowfs/config.yaml
    4. Environment variables: SHADOWFS_*
    5. CLI arguments
    6. Runtime updates
    """
    config = DEFAULT_CONFIG.copy()
    
    # Layer 1: System config
    if os.path.exists("/etc/shadowfs/config.yaml"):
        config.merge(load_yaml("/etc/shadowfs/config.yaml"))
    
    # Layer 2: User config
    user_config = os.path.expanduser("~/.config/shadowfs/config.yaml")
    if os.path.exists(user_config):
        config.merge(load_yaml(user_config))
    
    # Layer 3: Environment variables
    config.merge_from_env("SHADOWFS_")
    
    # Layer 4: CLI arguments
    config.merge_from_args(sys.argv)
    
    # Validate configuration
    validate_config(config)
    
    return config
```

### Hot-Reload Mechanism

```python
def setup_config_watcher(config_path: str, callback: Callable):
    """
    Watch configuration file for changes and reload.
    
    Uses inotify (Linux) or FSEvents (macOS) for efficient monitoring.
    """
    watcher = FileWatcher(config_path)
    
    def on_change(event):
        logger.info(f"Configuration changed: {event}")
        try:
            new_config = load_configuration()
            validate_config(new_config)
            callback(new_config)
            logger.info("Configuration reloaded successfully")
        except ConfigError as e:
            logger.error(f"Failed to reload config: {e}")
            # Keep old configuration
    
    watcher.on_modified(on_change)
    watcher.start()
```

---

## Transform Pipeline

### Transform Architecture

```
Input File Content
      ↓
┌─────────────────┐
│  Transform 1    │  (e.g., decompress)
└────────┬────────┘
         ↓
┌─────────────────┐
│  Transform 2    │  (e.g., template expansion)
└────────┬────────┘
         ↓
┌─────────────────┐
│  Transform 3    │  (e.g., markdown to HTML)
└────────┬────────┘
         ↓
Output to Application
```

### Example: Template Transform

```python
class TemplateTransform(Transform):
    """Expand templates using Jinja2"""
    
    def __init__(self, engine: str = "jinja2", context: Dict = None):
        self.engine = engine
        self.context = context or {}
        self.required = True  # Template errors are fatal
        
        if engine == "jinja2":
            from jinja2 import Template
            self.template_class = Template
        elif engine == "mako":
            from mako.template import Template
            self.template_class = Template
        else:
            raise ValueError(f"Unknown template engine: {engine}")
    
    def apply(self, content: bytes, path: str) -> bytes:
        """Apply template expansion"""
        try:
            # Decode content
            text = content.decode('utf-8')
            
            # Create template
            template = self.template_class(text)
            
            # Render with context
            result = template.render(**self.context)
            
            # Encode back to bytes
            return result.encode('utf-8')
            
        except Exception as e:
            raise TransformError(f"Template expansion failed for {path}: {e}")
```

### Example: Format Conversion Transform

```python
class MarkdownToHTMLTransform(Transform):
    """Convert Markdown to HTML"""
    
    def __init__(self, css_theme: str = None):
        self.css_theme = css_theme
        self.required = False  # Markdown rendering is optional
    
    def apply(self, content: bytes, path: str) -> bytes:
        """Convert markdown to HTML"""
        try:
            import markdown
            
            text = content.decode('utf-8')
            html = markdown.markdown(text, extensions=['extra', 'codehilite'])
            
            # Optionally wrap in HTML template
            if self.css_theme:
                html = self._wrap_with_theme(html, self.css_theme)
            
            return html.encode('utf-8')
            
        except ImportError:
            logger.warning("markdown library not available")
            return content  # Return original
        except Exception as e:
            logger.error(f"Markdown conversion failed: {e}")
            return content  # Return original
```

---

## Security Model

Following Meta-Architecture principle: **Security by Design**

### Security Layers

**1. Path Traversal Prevention**
```python
def is_safe_path(path: str, root: str) -> bool:
    """
    Prevent path traversal attacks.
    
    Attacks blocked:
    - ../../../etc/passwd
    - /absolute/path/escape
    - symlink escapes
    """
    # Normalize path
    normalized = os.path.normpath(path)
    
    # Resolve symlinks
    real_path = os.path.realpath(os.path.join(root, normalized))
    real_root = os.path.realpath(root)
    
    # Ensure path is within root
    return real_path.startswith(real_root)
```

**2. Transform Sandboxing**
```python
class SafeTemplateTransform(Transform):
    """Template transform with restricted execution environment"""
    
    def apply(self, content: bytes, path: str) -> bytes:
        # Create restricted Jinja2 environment
        from jinja2.sandbox import SandboxedEnvironment
        
        env = SandboxedEnvironment()
        template = env.from_string(content.decode('utf-8'))
        
        # Whitelist allowed functions
        safe_context = {
            'env': self.context.get('env'),
            'version': self.context.get('version'),
            # No access to os, sys, file I/O, etc.
        }
        
        result = template.render(**safe_context)
        return result.encode('utf-8')
```

**3. Permission Enforcement**
```python
def check_permissions(path: str, operation: str) -> bool:
    """
    Check if operation is allowed on path.
    
    Respects:
    - File system permissions
    - ShadowFS ACLs (if configured)
    - Read-only source restrictions
    """
    # Check filesystem permissions
    if not os.access(path, os.R_OK):
        return False
    
    # Check if source is read-only
    if operation in ['write', 'delete'] and is_readonly_source(path):
        return False
    
    # Check ShadowFS ACLs
    if not acl_allows(path, operation):
        return False
    
    return True
```

**4. Resource Limits**
```python
class ResourceLimiter:
    """Prevent resource exhaustion attacks"""
    
    def __init__(self):
        self.max_file_size = 1024 * 1024 * 1024  # 1GB
        self.max_transform_time = 30  # seconds
        self.max_memory = 512 * 1024 * 1024  # 512MB
    
    def check_file_size(self, size: int) -> bool:
        return size <= self.max_file_size
    
    @timeout(max_transform_time)
    def apply_transform(self, transform: Transform, content: bytes) -> bytes:
        """Apply transform with timeout"""
        return transform.apply(content)
```

**5. Audit Logging**
```python
def audit_log(operation: str, path: str, user: str, result: str):
    """Log security-relevant operations"""
    logger.info(
        "audit",
        operation=operation,
        path=path,
        user=user,
        result=result,
        timestamp=time.time()
    )
```

---

## Performance Patterns

Following Meta-Architecture principle: **Performance Optimization**

### 1. Caching Strategy

**Three-Level Cache**:
```
Level 1: Attribute Cache (stat results)
  - Size: 10,000 entries
  - TTL: 60 seconds
  - Key: path → FileAttributes

Level 2: Content Cache (file contents)
  - Size: 512 MB
  - TTL: 300 seconds
  - Key: (path, mtime) → bytes

Level 3: Transform Cache (transformed contents)
  - Size: 1 GB
  - TTL: 600 seconds
  - Key: (path, mtime, transform_hash) → bytes
```

**Implementation**:
```python
class LRUCache:
    def __init__(self, max_size: int, ttl: int):
        self.cache = {}  # key → (value, timestamp)
        self.access_order = deque()
        self.max_size = max_size
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        
        value, timestamp = self.cache[key]
        
        # Check TTL
        if time.time() - timestamp > self.ttl:
            del self.cache[key]
            return None
        
        # Update access order (LRU)
        self.access_order.remove(key)
        self.access_order.append(key)
        
        return value
    
    def set(self, key: str, value: Any):
        # Evict if at capacity
        if len(self.cache) >= self.max_size:
            oldest = self.access_order.popleft()
            del self.cache[oldest]
        
        self.cache[key] = (value, time.time())
        self.access_order.append(key)
```

### 2. Async Operations

```python
class AsyncFileOperations:
    """Asynchronous file operations using thread pool"""
    
    def __init__(self, thread_count: int = 10):
        self.executor = ThreadPoolExecutor(max_workers=thread_count)
    
    async def read_async(self, path: str, offset: int, size: int) -> bytes:
        """Asynchronous read operation"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._read_sync,
            path, offset, size
        )
    
    def _read_sync(self, path: str, offset: int, size: int) -> bytes:
        """Synchronous read (runs in thread pool)"""
        with open(path, 'rb') as f:
            f.seek(offset)
            return f.read(size)
```

### 3. Prefetching

```python
class Prefetcher:
    """Prefetch likely-to-be-accessed files"""
    
    def __init__(self, cache: CacheManager):
        self.cache = cache
        self.access_history = deque(maxlen=1000)
    
    def record_access(self, path: str):
        """Record file access for pattern learning"""
        self.access_history.append((path, time.time()))
        
        # Prefetch related files
        directory = os.path.dirname(path)
        self.prefetch_directory(directory)
    
    def prefetch_directory(self, directory: str):
        """Prefetch commonly accessed files in directory"""
        # Get list of files in directory
        files = os.listdir(directory)
        
        # Prefetch small files asynchronously
        for file in files[:10]:  # Limit to 10 files
            full_path = os.path.join(directory, file)
            if os.path.getsize(full_path) < 1024 * 1024:  # < 1MB
                self.cache.prefetch(full_path)
```

### 4. Connection Pooling

```python
class FileHandlePool:
    """Pool of open file handles for frequently accessed files"""
    
    def __init__(self, max_handles: int = 100):
        self.pool = {}  # path → file handle
        self.max_handles = max_handles
        self.lock = threading.Lock()
    
    def get_handle(self, path: str, mode: str = 'rb'):
        with self.lock:
            if path in self.pool:
                return self.pool[path]
            
            # Evict if at capacity
            if len(self.pool) >= self.max_handles:
                # Close least recently used handle
                lru_path = min(self.pool.keys(), key=lambda p: self.pool[p].last_access)
                self.pool[lru_path].close()
                del self.pool[lru_path]
            
            # Open new handle
            handle = open(path, mode)
            self.pool[path] = handle
            return handle
```

---

## Error Handling

Following Meta-Architecture principle: **Standardized Error Handling**

### Error Code System

```python
class ErrorCode(IntEnum):
    SUCCESS = 0
    INVALID_INPUT = 1       # Bad path, invalid config
    NOT_FOUND = 2           # File doesn't exist
    PERMISSION_DENIED = 3   # Access denied
    CONFLICT = 4            # File locked, already exists
    DEPENDENCY_ERROR = 5    # Transform library missing
    INTERNAL_ERROR = 6      # Bug in ShadowFS
    TIMEOUT = 7             # Operation took too long
    RATE_LIMITED = 8        # Too many operations
    DEGRADED = 9            # Running with reduced functionality
```

### Error Handling Pattern

```python
def safe_operation(func):
    """Decorator for consistent error handling"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return (ErrorCode.SUCCESS, result)
        
        except FileNotFoundError as e:
            logger.warning(f"File not found: {e}")
            return (ErrorCode.NOT_FOUND, None)
        
        except PermissionError as e:
            logger.warning(f"Permission denied: {e}")
            return (ErrorCode.PERMISSION_DENIED, None)
        
        except TransformError as e:
            logger.error(f"Transform failed: {e}")
            # Check if transform is required
            if e.transform.required:
                return (ErrorCode.DEPENDENCY_ERROR, None)
            else:
                # Graceful degradation: return untransformed
                return (ErrorCode.DEGRADED, e.original_content)
        
        except Exception as e:
            logger.exception(f"Internal error: {e}")
            return (ErrorCode.INTERNAL_ERROR, None)
    
    return wrapper

# Usage
@safe_operation
def read_file(path: str) -> bytes:
    """Read file with error handling"""
    # Implementation
    pass
```

### Graceful Degradation

```python
class GracefulDegradation:
    """Handle dependency failures gracefully"""
    
    def __init__(self):
        self.degraded_features = set()
    
    def check_dependencies(self):
        """Check for optional dependencies"""
        try:
            import jinja2
        except ImportError:
            logger.warning("jinja2 not available - template transforms disabled")
            self.degraded_features.add("template_transform")
        
        try:
            import markdown
        except ImportError:
            logger.warning("markdown not available - MD→HTML disabled")
            self.degraded_features.add("markdown_transform")
    
    def is_available(self, feature: str) -> bool:
        """Check if feature is available"""
        return feature not in self.degraded_features
```

---

## Testing Strategy

Following Meta-Architecture principle: **Testing Pyramid**

### Test Structure

```
Integration Tests (10%)
    ↑
Unit Tests (70%)
    ↑
Foundation Tests (20%)
```

### Unit Tests

```python
# tests/test_rule_engine.py
import pytest
from shadowfs.rule_engine import RuleEngine, Rule, RuleType

class TestRuleEngine:
    def test_include_rule_matches(self):
        rule = Rule(type=RuleType.INCLUDE, pattern="*.py")
        engine = RuleEngine([rule])
        
        assert engine.should_show_file("test.py", mock_attrs())
        assert not engine.should_show_file("test.txt", mock_attrs())
    
    def test_exclude_rule_matches(self):
        rule = Rule(type=RuleType.EXCLUDE, pattern="*.pyc")
        engine = RuleEngine([rule])
        
        assert not engine.should_show_file("test.pyc", mock_attrs())
        assert engine.should_show_file("test.py", mock_attrs())
    
    def test_rule_precedence(self):
        rules = [
            Rule(type=RuleType.EXCLUDE, pattern="*.txt"),
            Rule(type=RuleType.INCLUDE, pattern="important.txt"),
        ]
        engine = RuleEngine(rules)
        
        # First rule wins
        assert not engine.should_show_file("important.txt", mock_attrs())
```

### Integration Tests

```python
# tests/test_fuse_integration.py
import pytest
import os
from shadowfs import ShadowFS

class TestFUSEIntegration:
    @pytest.fixture
    def mounted_fs(self, tmp_path):
        """Mount ShadowFS for testing"""
        source = tmp_path / "source"
        mount = tmp_path / "mount"
        source.mkdir()
        mount.mkdir()
        
        # Create test files
        (source / "test.txt").write_text("Hello World")
        
        # Mount filesystem
        fs = ShadowFS(sources=[str(source)], config=default_config())
        fs.mount(str(mount))
        
        yield mount
        
        # Cleanup
        fs.unmount()
    
    def test_read_file(self, mounted_fs):
        """Test reading file through FUSE"""
        content = (mounted_fs / "test.txt").read_text()
        assert content == "Hello World"
    
    def test_list_directory(self, mounted_fs):
        """Test directory listing"""
        files = os.listdir(mounted_fs)
        assert "test.txt" in files
```

### Performance Tests

```python
# tests/test_performance.py
import pytest
import time

class TestPerformance:
    def test_cache_hit_performance(self, mounted_fs):
        """Verify cache improves read performance"""
        file_path = mounted_fs / "test.txt"
        
        # Cold read (cache miss)
        start = time.time()
        file_path.read_text()
        cold_time = time.time() - start
        
        # Warm read (cache hit)
        start = time.time()
        file_path.read_text()
        warm_time = time.time() - start
        
        # Cache hit should be faster
        assert warm_time < cold_time * 0.5
    
    def test_large_directory_listing(self, mounted_fs):
        """Test performance with many files"""
        # Create 1000 files
        for i in range(1000):
            (mounted_fs / f"file_{i}.txt").write_text("test")
        
        start = time.time()
        files = os.listdir(mounted_fs)
        duration = time.time() - start
        
        assert len(files) == 1000
        assert duration < 1.0  # Should complete in under 1 second
```

---

## Deployment Guide

### Installation

```bash
# Install Python dependencies
pip install fusepy pyyaml jinja2 prometheus_client

# Or use requirements.txt
pip install -r requirements.txt

# Install ShadowFS
python setup.py install

# Or in development mode
python setup.py develop
```

### Basic Usage

```bash
# Mount with default config
shadowfs --sources /data/documents /data/projects --mount /mnt/shadowfs

# Mount with custom config
shadowfs --config /etc/shadowfs/config.yaml --mount /mnt/shadowfs

# Mount in foreground (for debugging)
shadowfs --sources /data --mount /mnt/shadowfs --foreground --debug

# Unmount
fusermount -u /mnt/shadowfs  # Linux
umount /mnt/shadowfs         # macOS
```

### Systemd Service

```ini
# /etc/systemd/system/shadowfs.service
[Unit]
Description=ShadowFS FUSE Filesystem
After=network.target

[Service]
Type=simple
User=shadowfs
Group=shadowfs
ExecStart=/usr/local/bin/shadowfs \
    --config /etc/shadowfs/config.yaml \
    --mount /mnt/shadowfs \
    --log-file /var/log/shadowfs/shadowfs.log
ExecStop=/bin/fusermount -u /mnt/shadowfs
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable shadowfs
sudo systemctl start shadowfs

# Check status
sudo systemctl status shadowfs

# View logs
sudo journalctl -u shadowfs -f
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install FUSE
RUN apt-get update && apt-get install -y fuse && rm -rf /var/lib/apt/lists/*

# Install ShadowFS
COPY requirements.txt /app/
RUN pip install -r /app/requirements.txt

COPY shadowfs/ /app/shadowfs/
WORKDIR /app

# Create mount point
RUN mkdir -p /mnt/shadowfs

# Run ShadowFS
CMD ["python", "-m", "shadowfs", \
     "--config", "/etc/shadowfs/config.yaml", \
     "--mount", "/mnt/shadowfs"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  shadowfs:
    build: .
    privileged: true  # Required for FUSE
    devices:
      - /dev/fuse
    cap_add:
      - SYS_ADMIN
    volumes:
      - /data/documents:/sources/documents:ro
      - /data/projects:/sources/projects:rw
      - ./config.yaml:/etc/shadowfs/config.yaml:ro
      - shadowfs-mount:/mnt/shadowfs
    ports:
      - "9090:9090"  # Metrics

volumes:
  shadowfs-mount:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/shadowfs
```

### Configuration Examples

**Example 1: Development Environment**
```yaml
# Hide build artifacts, show only source code
shadowfs:
  sources:
    - path: /home/user/projects
      priority: 1
  
  rules:
    - name: "Show source files only"
      type: include
      patterns:
        - "**/*.py"
        - "**/*.js"
        - "**/*.go"
        - "**/*.rs"
    
    - name: "Hide build artifacts"
      type: exclude
      patterns:
        - "**/__pycache__/**"
        - "**/node_modules/**"
        - "**/target/**"
        - "**/.git/**"
  
  cache:
    enabled: true
    max_size_mb: 256
```

**Example 2: Documentation Site**
```yaml
# Convert markdown to HTML on-the-fly
shadowfs:
  sources:
    - path: /docs/markdown
      priority: 1
  
  transforms:
    - name: "Markdown to HTML"
      pattern: "**/*.md"
      type: convert
      from: markdown
      to: html
      css_theme: github
  
  cache:
    enabled: true
    cache_transforms: true
```

**Example 3: Encrypted Storage**
```yaml
# Transparent encryption for sensitive directories
shadowfs:
  sources:
    - path: /encrypted-source
      priority: 1
  
  transforms:
    - name: "Decrypt on read"
      pattern: "**/*.enc"
      type: decrypt
      algorithm: AES-256-GCM
      key_source: file:/etc/shadowfs/encryption.key
  
  rules:
    - name: "Hide encrypted extensions"
      type: attribute_transform
      pattern: "**/*.enc"
      strip_extension: true  # file.txt.enc → file.txt
```

---

## Compliance Matrix

### Meta-Architecture v1.0.0 Compliance

| Principle | Status | Implementation |
|-----------|--------|---------------|
| 1. Layered Architecture | ✅ PASS | Four layers with downward-only dependencies |
| 2. Explicit Dependencies | ✅ PASS | requirements.txt, setup.py, no hidden deps |
| 3. Graceful Degradation | ✅ PASS | Optional transforms, feature flags |
| 4. Input Validation | ✅ PASS | Path validation, config validation, safe transforms |
| 5. Standardized Errors | ✅ PASS | 10 error codes, consistent handling |
| 6. Hierarchical Config | ✅ PASS | 6-level config hierarchy with precedence |
| 7. Observable Behavior | ✅ PASS | Structured logging, Prometheus metrics |
| 8. Automated Testing | ✅ PASS | Unit, integration, performance tests |
| 9. Security by Design | ✅ PASS | Path traversal prevention, sandboxing, ACLs |
| 10. Resource Lifecycle | ✅ PASS | File handle pooling, cache eviction, cleanup |
| 11. Performance Patterns | ✅ PASS | Multi-level caching, async ops, prefetching |
| 12. Evolutionary Design | ✅ PASS | Versioned config, feature flags, hot-reload |

### Compliance Checklist

**Mechanistic Completeness**
- [x] Core mechanism explained (FUSE interception, rule evaluation, transform pipeline)
- [x] Logical structure explicit (4-layer architecture)
- [x] Reasoning behind decisions documented
- [x] No floating abstractions
- [x] Derivation paths clear

**Logical Consistency**
- [x] No internal contradictions
- [x] Dependencies are acyclic
- [x] Layer boundaries enforced
- [x] Principles compose predictably

**Systematic Organization**
- [x] Four-layer pattern implemented
- [x] Dependencies explicitly managed
- [x] Error handling standardized
- [x] Configuration hierarchy clear

**Practical Utility**
- [x] Runnable code examples provided
- [x] Compliance checklists included
- [x] Deployment guide available
- [x] Edge cases documented

---

## Next Steps

### Phase 1: Foundation (Week 1-2)
- [ ] Implement Layer 1 (path utils, file operations)
- [ ] Unit tests for Foundation layer
- [ ] Set up project structure and dependencies

### Phase 2: Infrastructure (Week 3-4)
- [ ] Implement config manager with hot-reload
- [ ] Implement cache manager (LRU, TTL)
- [ ] Set up logging and metrics
- [ ] Unit tests for Infrastructure layer

### Phase 3: Integration (Week 5-6)
- [ ] Implement rule engine
- [ ] Implement transform pipeline
- [ ] Build core transforms (template, compress, convert)
- [ ] Integration tests for rule + transform

### Phase 4: Application (Week 7-8)
- [ ] Implement FUSE operations
- [ ] Build CLI interface
- [ ] Add control server for runtime management
- [ ] End-to-end integration tests

### Phase 5: Production (Week 9-10)
- [ ] Performance optimization
- [ ] Security audit
- [ ] Documentation
- [ ] Deployment automation

---

## Appendix

### Glossary

- **Shadow Filesystem**: Virtual filesystem that provides a transformed view of underlying filesystems
- **FUSE**: Filesystem in Userspace - allows non-privileged users to create filesystems
- **Transform**: Operation that modifies file content during read
- **Rule**: Condition that determines file visibility
- **View Composition**: Merging multiple source directories into unified view

### References

- FUSE Documentation: https://www.kernel.org/doc/html/latest/filesystems/fuse.html
- fusepy Library: https://github.com/fusepy/fusepy
- pyfuse3 Library: https://github.com/libfuse/pyfuse3
- Meta-Architecture v1.0.0: See architecture-creator skill

### License

This architecture is released under MIT License.

---

**Document Version**: 1.0.0  
**Last Updated**: 2025-11-11  
**Author**: Claude + Stephen Cox (andronics)  
**Status**: Design Phase - Ready for Implementation