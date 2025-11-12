# ShadowFS: Dynamic Filesystem Transformation Layer

**A FUSE-based filesystem that provides dynamic filtering, transformation, and virtual organizational views over existing filesystems.**

## 📋 Implementation Status

**Current Phase**: Planning Complete - Ready for Phase 0
**Implementation Plan**: See [PLAN.md](PLAN.md) for detailed roadmap
**Timeline**: 14 weeks to v1.0.0

> **Important**: Always keep PLAN.md updated as phases complete. Mark completed items, update timelines, and document any deviations from the original plan.

---

## Project Vision

ShadowFS creates a "shadow layer" over your existing filesystems, enabling:

- **Dynamic Filtering**: Show/hide files based on runtime-configurable rules
- **On-the-Fly Transformation**: Convert, compress, encrypt, or template files transparently during read
- **Virtual Organization**: Create multiple directory structures (by type, date, tags, etc.) over the same files without duplication
- **Zero Overhead**: Files remain in place - no copying, no storage overhead

Think of it as "virtual filesystem middleware" that sits between applications and your files, providing programmable views and transformations.

---

## Core Concepts

### The Shadow Filesystem Analogy

Just like TypeScript's `.d.ts` files create a "shadow" type layer over JavaScript code, ShadowFS creates a shadow organizational and transformation layer over your existing files.

**Reference**: See [docs/typescript-type-discovery.md](docs/typescript-type-discovery.md) for the mental model that inspired this architecture.

### Core Pillars of ShadowFS

```
┌─────────────────────────────────────────────────────┐
│                  Application Layer                   │
│              (Your tools and programs)               │
└────────────────────┬────────────────────────────────┘
                     │
          ╔══════════▼══════════╗
          ║   ShadowFS Layer    ║
          ║                     ║
          ║  1. Filters         ║ ◄─── Show/hide files by rules
          ║  2. Transforms      ║ ◄─── Modify content on-the-fly
          ║  3. Virtual Layers  ║ ◄─── Multiple organizational views
          ║  4. Middleware      ║ ◄─── Advanced capabilities (Phase 7+)
          ╚══════════╤══════════╝
                     │
┌────────────────────▼────────────────────────────────┐
│              Real Filesystem(s)                      │
│         /source/documents  /source/projects          │
└─────────────────────────────────────────────────────┘
```

**Note**: Middleware extensions (deduplication, versioning, encryption, search, etc.) are future enhancements planned for Phase 7+. See [docs/middleware-ideas.md](docs/middleware-ideas.md).

---

## Quick Start

### Installation

```bash
# Install dependencies
pip install fusepy pyyaml jinja2

# Install ShadowFS
git clone https://github.com/andronics/shadowfs.git
cd shadowfs
python setup.py install
```

### Basic Usage

```bash
# Mount with simple configuration
shadowfs --sources /data/projects --mount /mnt/shadowfs

# Mount with custom config
shadowfs --config shadowfs.yaml --mount /mnt/shadowfs

# Explore virtual layers
ls /mnt/shadowfs/by-type/
ls /mnt/shadowfs/by-date/2024/11/
```

### Example Configuration

```yaml
shadowfs:
  sources:
    - path: /source/projects
      priority: 1

  # Filter: hide build artifacts
  rules:
    - name: "Hide build files"
      type: exclude
      patterns:
        - "**/__pycache__/**"
        - "**/node_modules/**"

  # Transform: convert markdown to HTML
  transforms:
    - name: "Markdown to HTML"
      pattern: "**/*.md"
      type: convert
      from: markdown
      to: html

  # Virtual layer: organize by file type
  layers:
    - name: by-type
      type: classifier
      classifier: extension
      mappings:
        ".py": python
        ".js": javascript
        ".md": docs
```

**Result**: Access your files through multiple views:
```
/mnt/shadowfs/
├── by-type/
│   ├── python/
│   │   └── project.py
│   └── docs/
│       └── README.md (→ HTML)
```

---

## Documentation

### Core Architecture

**📄 [docs/architecture.md](docs/architecture.md)** - *Main architecture document*

Comprehensive system design covering:
- **The Core Mechanism**: How FUSE interception works
- **4-Layer Architecture**: Foundation → Infrastructure → Integration → Application
- **Component Specifications**: Detailed design of each subsystem
- **Configuration System**: Hierarchical config with hot-reload
- **Transform Pipeline**: Chain transformations on file content
- **Security Model**: Path traversal prevention, sandboxing, ACLs
- **Performance Patterns**: Multi-level caching, async operations
- **Error Handling**: Standardized error codes and graceful degradation
- **Testing Strategy**: Unit, integration, and performance tests
- **Deployment Guide**: Installation, systemd service, Docker

**Key Sections**:
- Layer 1 (Foundation): Path utilities, file operations, validators
- Layer 2 (Infrastructure): Config manager, cache, logging, metrics
- Layer 3 (Integration): Rule engine, transform pipeline, pattern matching
- Layer 4 (Application): FUSE operations, main entry point, control server

**Compliance**: Meta-Architecture v1.0.0 compliant

---

### Virtual Layers System

**📄 [docs/virtual-layers.md](docs/virtual-layers.md)** - *Virtual organizational views*

Design for creating multiple directory structures over the same files:

**Core Features**:
- **Virtual Layer Types**:
  - Classifier Layers (by extension, size, MIME type)
  - Tag Layers (by metadata)
  - Date Layers (YYYY/MM/DD hierarchy)
  - Hierarchical Layers (multi-level structures)
  - Pattern Layers (rule-based classification)

- **The Mechanism**:
  - Path interception and resolution
  - Reverse index: `category → files`
  - Dynamic index updates
  - Cached path resolution

**Example Use Cases**:
```yaml
# Development environment
by-type/
  python/ → *.py files
  javascript/ → *.js files

# Photo library
by-date/
  2024/11/11/ → photos from Nov 11

by-camera/
  Canon/ → Canon camera photos

# Code repository
by-project/
  projectA/
    src/ → source files
    tests/ → test files
```

**Advanced Features**:
- Incremental index updates
- Writable virtual layers
- Computed virtual files
- Git-aware organization

---

### Knowledge Base

**📄 [docs/typescript-type-discovery.md](docs/typescript-type-discovery.md)** - *Conceptual foundation*

The "shadow filesystem" mental model came from understanding TypeScript's type discovery:
- `.d.ts` files shadow JavaScript implementations
- Multiple lookup paths (local, package, @types)
- Separation of interface and implementation
- Convention-based discovery

**Key Insight**: Just as TypeScript creates a type layer over JavaScript, ShadowFS creates organizational and transformation layers over filesystems.

---

### Middleware Extensions

**📄 [docs/middleware-ideas.md](docs/middleware-ideas.md)** - *Advanced middleware patterns*

10 proven middleware patterns from the FUSE ecosystem that can extend ShadowFS:

**Storage Optimization**:
- Deduplication (10x-100x savings for backups)
- Compression (3x-10x savings for text)
- Content-Addressed Storage (natural deduplication)

**Security & Compliance**:
- Encryption (AES-256-GCM transparent encryption)
- Audit Logging (security & compliance)
- Quota & Rate Limiting (multi-tenant control)

**Advanced Features**:
- Versioning (time-travel filesystem)
- Git Integration (auto-commit on write)
- Full-Text Search (inotify-based indexing)
- Cloud Sync (S3/Drive/Dropbox)

**Middleware Stacking**: Compose multiple middleware in a pipeline for powerful combinations like backup systems (Dedup → Compress → Encrypt → Cloud Sync).

---

## Project Structure

**Note**: This structure uses a feature-based organization that groups related functionality together, replacing the previous strict 4-layer architecture (foundation/infrastructure/integration/application).

```
shadowfs/
├── CLAUDE.md                          # ← This file
├── PLAN.md                            # Implementation roadmap
├── docs/
│   ├── architecture.md                # Main architecture (Meta-Architecture v1.0.0)
│   ├── middleware-ideas.md            # Middleware extension patterns
│   ├── virtual-layers.md              # Virtual layers design
│   └── typescript-type-discovery.md   # Conceptual foundation
│
├── shadowfs/
│   ├── __init__.py
│   │
│   ├── core/                          # Shared utilities (foundation + infrastructure)
│   │   ├── __init__.py
│   │   ├── cache.py                   # CacheManager (was infrastructure/cache_manager.py)
│   │   ├── config.py                  # ConfigManager (was infrastructure/config_manager.py)
│   │   ├── constants.py               # System constants (was foundation/constants.py)
│   │   ├── file_ops.py                # Safe file I/O (was foundation/file_operations.py)
│   │   ├── logging.py                 # Structured logging (was infrastructure/logger.py)
│   │   ├── metrics.py                 # Performance metrics (was infrastructure/metrics.py)
│   │   ├── path_utils.py              # Path utilities (was foundation/path_utils.py)
│   │   └── validators.py              # Input validation (was foundation/validators.py)
│   │
│   ├── layers/                # Virtual layer system (complete feature)
│   │   ├── __init__.py
│   │   ├── base.py                    # Layer base class
│   │   ├── classifier.py              # ClassifierLayer (was classifier_layer.py)
│   │   ├── date.py                    # DateLayer (was date_layer.py)
│   │   ├── hierarchical.py            # HierarchicalLayer (was hierarchical_layer.py)
│   │   ├── tag.py                     # TagLayer (was tag_layer.py)
│   │   └── manager.py                 # LayerManager
│   │
│   ├── rules/                         # Rule system (complete feature)
│   │   ├── __init__.py
│   │   ├── engine.py                  # RuleEngine (was integration/rule_engine.py)
│   │   └── patterns.py                # PatternMatcher (was integration/pattern_matcher.py)
│   │
│   ├── transforms/                    # Transform system (complete feature)
│   │   ├── __init__.py
│   │   ├── base.py                    # Transform base class
│   │   ├── compression.py             # gzip/bz2/lzma
│   │   ├── format_conversion.py       # MD→HTML, CSV→JSON
│   │   ├── pipeline.py                # TransformPipeline (was integration/transform_pipeline.py)
│   │   └── template.py                # Jinja2 templates
│   │
│   ├── fuse/                          # FUSE interface (complete feature)
│   │   ├── __init__.py
│   │   ├── operations.py              # ShadowFSOperations (was application/fuse_operations.py)
│   │   └── control.py                 # ControlServer (was application/control_server.py)
│   │
│   ├── cli.py                         # CLI entry point (was application/cli.py)
│   └── main.py                        # Main entry point (was application/shadowfs_main.py)
│
│   └── middleware/                    # Phase 7: Middleware extensions (future)
│       ├── __init__.py
│       ├── base.py                    # Middleware base class
│       ├── deduplication.py           # Block-level dedup
│       ├── versioning.py              # Time-travel filesystem
│       ├── compression_mw.py          # Transparent compression
│       ├── encryption_mw.py           # Transparent encryption
│       ├── search_index.py            # Full-text search
│       ├── git_aware.py               # Git integration
│       ├── cloud_sync.py              # S3/Drive/Dropbox sync
│       ├── cas.py                     # Content-addressed storage
│       ├── quota.py                   # Quota & rate limiting
│       └── audit.py                   # Audit logging
│
├── tests/                             # Mirror source structure
│   ├── core/                          # Core module tests
│   ├── layers/                # Virtual layers tests
│   ├── rules/                         # Rules system tests
│   ├── transforms/                    # Transforms tests
│   ├── fuse/                          # FUSE interface tests
│   ├── integration/                   # End-to-end tests
│   ├── test_cli.py                    # CLI tests
│   └── test_main.py                   # Main entry point tests
│
├── config/
│   ├── shadowfs.yaml                  # Example config
│   └── templates/
│       ├── development.yaml
│       ├── photos.yaml
│       └── documents.yaml
│
├── scripts/
│   ├── mount.sh
│   ├── unmount.sh
│   └── validate_config.py
│
├── requirements.txt
├── setup.py
├── README.md
└── LICENSE
```

### Import Examples (Updated for New Structure)

```python
# Core utilities
from shadowfs.core.cache import CacheManager
from shadowfs.core.config import ConfigManager
from shadowfs.core import constants, logging, path_utils

# Virtual layers
from shadowfs.layers import LayerManager
from shadowfs.layers.classifier import ClassifierLayer

# Rules system
from shadowfs.rules import RuleEngine, PatternMatcher
from shadowfs.rules.engine import Rule, RuleAction

# Transforms
from shadowfs.transforms import TransformPipeline
from shadowfs.transforms.compression import CompressionTransform

# FUSE interface
from shadowfs.fuse import ShadowFSOperations, ControlServer

# Entry points
from shadowfs import cli, main
```

---

## Key Components

### 1. Rule Engine

**Location**: `shadowfs/integration/rule_engine.py`

**Purpose**: Determines file visibility based on configurable rules

**Reference**: [docs/architecture.md § Rule Evaluation Logic](docs/architecture.md#rule-evaluation-logic)

**Key Features**:
- Pattern matching (glob, regex)
- Attribute conditions (size, date, permissions)
- Logical operators (AND, OR, NOT)
- First-match-wins precedence

**Example**:
```python
from shadowfs.rule_engine import RuleEngine, Rule, RuleType

rules = [
    Rule(type=RuleType.EXCLUDE, pattern="*.pyc"),
    Rule(type=RuleType.INCLUDE, pattern="*.py"),
]

engine = RuleEngine(rules)
if engine.should_show_file("test.py", file_attrs):
    # File is visible
```

---

### 2. Transform Pipeline

**Location**: `shadowfs/integration/transform_pipeline.py`

**Purpose**: Apply transformations to file content during read

**Reference**: [docs/architecture.md § Transform Pipeline](docs/architecture.md#transform-pipeline)

**Key Features**:
- Chain multiple transforms
- Graceful degradation for optional transforms
- Transform caching for performance
- Plugin architecture for custom transforms

**Built-in Transforms**:
- `TemplateTransform`: Jinja2/Mako expansion
- `CompressionTransform`: gzip/bz2/lzma
- `EncryptionTransform`: AES-256, ChaCha20
- `FormatConversionTransform`: MD→HTML, CSV→JSON

**Example**:
```python
from shadowfs.transform_pipeline import TransformPipeline
from shadowfs.transforms import MarkdownToHTMLTransform

pipeline = TransformPipeline()
pipeline.add_transform(MarkdownToHTMLTransform(css_theme="github"))

content = pipeline.apply(original_bytes, "README.md")
```

---

### 3. Virtual Layer System

**Location**: `shadowfs/layers/`

**Purpose**: Create multiple organizational views over same files

**Reference**: [docs/virtual-layers.md](docs/virtual-layers.md)

**Status**: ✅ Complete (Phase 4)

**Key Classes**:
- `Layer` (base): Abstract interface for all layers
- `ClassifierLayer`: Organize by file properties (extension, size, MIME, pattern, git status)
- `DateLayer`: Time-based hierarchy (YYYY/MM/DD)
- `TagLayer`: Organize by metadata tags (xattr, sidecar files, patterns)
- `HierarchicalLayer`: Multi-level structures (project/type, arbitrary depth)
- `LayerManager`: Coordinates all layers
- `LayerFactory`: Factory functions for common configurations

**Quick Start**:
```python
from shadowfs.layers import (
    LayerManager,
    LayerFactory,
)

# Create manager with source directories
manager = LayerManager(["/data/projects", "/data/docs"])

# Add layers using factory
manager.add_layer(LayerFactory.create_extension_layer("by-type"))
manager.add_layer(LayerFactory.create_date_layer("by-date"))
manager.add_layer(LayerFactory.create_size_layer("by-size"))

# Scan and build indexes
manager.scan_sources()
manager.rebuild_indexes()

# Resolve virtual paths
real_path = manager.resolve_path("by-type/py/project.py")
# Returns: /data/projects/project.py

# List virtual directories
types = manager.list_directory("by-type")
# Returns: ['py', 'js', 'md', ...]

years = manager.list_directory("by-date")
# Returns: ['2023', '2024', '2025']
```

**Advanced Usage - Custom Layers**:
```python
from shadowfs.layers import (
    ClassifierLayer,
    DateLayer,
    TagLayer,
    HierarchicalLayer,
    ClassifierBuiltins,
    HierarchicalBuiltins,
    TagExtractors,
)

# Classifier layer with built-in classifiers
extension_layer = ClassifierLayer("by-type", ClassifierBuiltins.extension)
size_layer = ClassifierLayer("by-size", ClassifierBuiltins.size)
mime_layer = ClassifierLayer("by-mime", ClassifierBuiltins.mime_type)

# Date layer (mtime, ctime, or atime)
date_layer = DateLayer("by-modified", "mtime")

# Tag layer with multiple extractors
tag_layer = TagLayer("by-tag", [
    TagExtractors.xattr(),                          # Extended attributes
    TagExtractors.sidecar(".tags"),                 # Sidecar files
    TagExtractors.filename_pattern("*important*", ["important"]),
    TagExtractors.extension_map({".py": ["code", "python"]}),
])

# Hierarchical layer with custom classifiers
project_layer = HierarchicalLayer("by-project", [
    HierarchicalBuiltins.by_path_component(0),      # First directory = project
    HierarchicalBuiltins.by_path_component(1),      # Second directory = category
])

# Add all layers to manager
for layer in [extension_layer, size_layer, date_layer, tag_layer, project_layer]:
    manager.add_layer(layer)

manager.rebuild_indexes()
```

**Layer Types**:

1. **ClassifierLayer** - Organize by single property
   - Built-in classifiers: extension, size, mime_type, pattern, git_status
   - Custom: `lambda file_info: <category>`

2. **DateLayer** - Three-level date hierarchy (YYYY/MM/DD)
   - Fields: mtime (modification), ctime (creation), atime (access)

3. **TagLayer** - Multi-tag support (one file in multiple categories)
   - Extractors: xattr, sidecar files, patterns, extension mapping

4. **HierarchicalLayer** - N-level hierarchies
   - Classifiers: path component, extension group, size range
   - Custom: chain multiple classifiers

**Statistics and Management**:
```python
# Get manager statistics
stats = manager.get_stats()
print(f"Sources: {stats['source_count']}")
print(f"Layers: {stats['layer_count']}")
print(f"Files: {stats['file_count']}")

# List all layers
layers = manager.list_layers()
# Returns: ['by-type', 'by-date', 'by-size', ...]

# Get specific layer
layer = manager.get_layer("by-type")

# Remove layer
manager.remove_layer("by-size")

# Clear everything
manager.clear_all()
```

**Complete Example - Photo Organization**:
```python
from shadowfs.layers import (
    LayerManager,
    DateLayer,
    TagLayer,
    TagExtractors,
)

# Create manager for photo library
manager = LayerManager(["/photos"])

# Organize by date taken
date_layer = DateLayer("by-date", "mtime")
manager.add_layer(date_layer)

# Organize by tags from xattr and sidecar files
tag_layer = TagLayer("by-tag", [
    TagExtractors.xattr(),
    TagExtractors.sidecar(".tags"),
])
manager.add_layer(tag_layer)

# Scan photos and build indexes
manager.scan_sources()
manager.rebuild_indexes()

# Access photos by date
photos_nov_12 = manager.list_directory("by-date/2024/11/12")

# Access photos by tag
family_photos = manager.list_directory("by-tag/family")
vacation_photos = manager.list_directory("by-tag/vacation")

# Same photo can appear in multiple virtual locations
# /photos/IMG_1234.jpg appears as:
#   - by-date/2024/11/12/IMG_1234.jpg
#   - by-tag/family/IMG_1234.jpg
#   - by-tag/vacation/IMG_1234.jpg
```

---

### 4. Configuration Manager

**Location**: `shadowfs/infrastructure/config_manager.py`

**Purpose**: Load and manage hierarchical configuration

**Reference**: [docs/architecture.md § Configuration System](docs/architecture.md#configuration-system)

**Configuration Hierarchy** (lowest to highest precedence):
1. Compiled defaults
2. System config: `/etc/shadowfs/config.yaml`
3. User config: `~/.config/shadowfs/config.yaml`
4. Environment variables: `SHADOWFS_*`
5. CLI arguments
6. Runtime updates

**Features**:
- Hot-reload without unmounting
- Schema validation
- Secure defaults
- Precedence resolution

**Example**:
```python
from shadowfs.config_manager import ConfigManager

config = ConfigManager()
config.load_config("shadowfs.yaml")

# Hot-reload on file change
config.watch_file(on_change=lambda: print("Config reloaded"))

# Access configuration
for layer in config.layers:
    print(f"Virtual layer: {layer.name}")
```

---

### 5. Cache Manager

**Location**: `shadowfs/infrastructure/cache_manager.py`

**Purpose**: Multi-level caching for performance

**Reference**: [docs/architecture.md § Performance Patterns](docs/architecture.md#performance-patterns)

**Cache Levels**:
- **L1**: File attributes (stat results) - 10K entries, 60s TTL
- **L2**: File content - 512MB, 300s TTL
- **L3**: Transformed content - 1GB, 600s TTL

**Features**:
- LRU eviction
- TTL expiration
- Size-based limits
- Selective invalidation

**Example**:
```python
from shadowfs.cache_manager import CacheManager

cache = CacheManager(max_size_mb=512, ttl_seconds=300)

# Cache file content
cache.set("path/to/file", file_content)

# Retrieve from cache
content = cache.get("path/to/file")

# Invalidate specific path
cache.invalidate_path("path/to/file")
```

---

### 6. FUSE Operations

**Location**: `shadowfs/layer4_application/fuse_operations.py`

**Purpose**: Implement FUSE filesystem callbacks

**Reference**: [docs/architecture.md § Component Specifications](docs/architecture.md#component-specifications)

**Key Operations**:
- `getattr()`: Get file attributes (stat)
- `readdir()`: List directory contents
- `open()`: Open file for reading/writing
- `read()`: Read file content
- `write()`: Write file content (if write-through enabled)
- `release()`: Close file

**Integration Points**:
- Virtual Layer Router (path resolution)
- Rule Engine (visibility filtering)
- Transform Pipeline (content modification)
- Cache Manager (performance optimization)

**Example Flow**:
```
1. Application: open("/mnt/shadowfs/by-type/python/file.py")
2. FUSE Kernel → ShadowFS.open()
3. Virtual Layer Router: "by-type/python/file.py" → "/source/file.py"
4. Rule Engine: Check visibility rules
5. Cache: Check if attributes cached
6. OS: os.open("/source/file.py")
7. Return file handle to application
```

---

## Development Roadmap

> **📌 Note**: This roadmap is now tracked in detail in [PLAN.md](PLAN.md). The information below is a summary. Always refer to PLAN.md for the authoritative implementation plan and update it as work progresses.

### Quick Reference

- **Phase 0**: Development Infrastructure (Week 1) - **MUST BE COMPLETED FIRST**
- **Phase 1**: Foundation Layer (Weeks 2-3)
- **Phase 2**: Infrastructure Layer (Weeks 4-5)
- **Phase 3**: Integration - Rules & Transforms (Weeks 6-7)
- **Phase 4**: Integration - Virtual Layers (Weeks 8-9)
- **Phase 5**: Application Layer (Weeks 10-11)
- **Phase 6**: Production Readiness (Weeks 12-14)
- **Phase 7**: Middleware Extensions (Future)

For detailed tasks, acceptance criteria, and parallelization opportunities, see [PLAN.md](PLAN.md).

### Phase 0: Development Infrastructure (Week 1) - CRITICAL
**Status**: Not Started
**Reference**: [PLAN.md § Phase 0](PLAN.md#phase-0-development-infrastructure-week-1)

This phase MUST be completed before any other work begins. It establishes:
- CI/CD pipeline with automated quality gates
- Test infrastructure with 100% coverage requirement
- Pre-commit hooks and development scripts
- All project configuration files

### Phase 1: Foundation (Weeks 2-3)
**Status**: Not Started

**Tasks**:
- [ ] Implement Layer 1 (Foundation)
  - [ ] `path_utils.py`: Path normalization and validation
  - [ ] `file_operations.py`: Safe file I/O wrappers
  - [ ] `validators.py`: Input validation functions
  - [ ] `constants.py`: System constants
- [ ] Unit tests for Foundation layer
- [ ] Project structure setup
- [ ] Dependency management (requirements.txt, setup.py)

**Reference**: [docs/architecture.md § Layer 1: Foundation](docs/architecture.md#layer-1-foundation-primitives)

---

### Phase 2: Infrastructure (Weeks 3-4)
**Status**: Not Started

**Tasks**:
- [ ] Implement Layer 2 (Infrastructure)
  - [ ] `config_manager.py`: Hierarchical configuration with hot-reload
  - [ ] `cache_manager.py`: LRU cache with TTL
  - [ ] `logger.py`: Structured logging
  - [ ] `metrics.py`: Performance metrics (Prometheus)
- [ ] Configuration file schema validation
- [ ] Unit tests for Infrastructure layer

**Reference**: [docs/architecture.md § Layer 2: Infrastructure](docs/architecture.md#layer-2-infrastructure-core-services)

---

### Phase 3: Integration - Rules & Transforms (Weeks 5-6)
**Status**: Not Started

**Tasks**:
- [ ] Implement Layer 3 (Integration) - Part 1
  - [ ] `rule_engine.py`: Rule evaluation engine
  - [ ] `pattern_matcher.py`: Glob and regex matching
  - [ ] `transform_pipeline.py`: Transform chain executor
  - [ ] Core transforms:
    - [ ] `template.py`: Jinja2 template expansion
    - [ ] `compression.py`: gzip/bz2/lzma
    - [ ] `format_conversion.py`: Markdown→HTML
- [ ] Integration tests for rules + transforms
- [ ] Performance benchmarking

**Reference**: [docs/architecture.md § Layer 3: Integration](docs/architecture.md#layer-3-integration-external-systems)

---

### Phase 4: Integration - Virtual Layers (Weeks 7-8)
**Status**: Not Started

**Tasks**:
- [ ] Implement virtual layers system
  - [ ] `base.py`: Layer abstract base class
  - [ ] `classifier_layer.py`: Classifier-based organization
  - [ ] `tag_layer.py`: Tag-based organization
  - [ ] `date_layer.py`: Date-based hierarchy
  - [ ] `hierarchical_layer.py`: Multi-level structures
  - [ ] `manager.py`: LayerManager
- [ ] Built-in classifiers (extension, size, MIME type)
- [ ] Index building and caching
- [ ] Integration tests for virtual layers

**Reference**: [docs/virtual-layers.md](docs/virtual-layers.md)

---

### Phase 5: Application Layer (Weeks 9-10)
**Status**: Not Started

**Tasks**:
- [ ] Implement Layer 4 (Application)
  - [ ] `fuse_operations.py`: FUSE filesystem callbacks
  - [ ] `shadowfs_main.py`: Main entry point
  - [ ] `control_server.py`: Runtime control API
  - [ ] `cli.py`: Command-line interface
- [ ] Virtual layer path routing
- [ ] End-to-end integration tests
- [ ] CLI implementation and testing

**Reference**: [docs/architecture.md § Layer 4: Application](docs/architecture.md#layer-4-application-business-logic)

---

### Phase 6: Production Readiness (Weeks 11-12)
**Status**: Not Started

**Tasks**:
- [ ] Performance optimization
  - [ ] Profile and optimize hot paths
  - [ ] Tune cache sizes and TTLs
  - [ ] Async operations for I/O
- [ ] Security audit
  - [ ] Path traversal testing
  - [ ] Input validation review
  - [ ] Transform sandboxing verification
- [ ] Documentation
  - [ ] User guide
  - [ ] Configuration reference
  - [ ] API documentation
- [ ] Deployment automation
  - [ ] Systemd service files
  - [ ] Docker containers
  - [ ] Installation scripts

**Reference**: [docs/architecture.md § Deployment Guide](docs/architecture.md#deployment-guide)

---

### Phase 7: Middleware Extensions (Weeks 13+)
**Status**: Future Enhancement

**Overview**: Advanced middleware patterns from proven FUSE implementations that extend ShadowFS capabilities.

**Reference**: [docs/middleware-ideas.md](docs/middleware-ideas.md)

**Middleware Components**:

1. **Deduplication Middleware**
   - Block-level content deduplication using SHA256 hashing
   - 10x-100x storage savings for backup scenarios
   - Use cases: Backup storage, VM images, development environments

2. **Versioning Middleware (Time-Travel)**
   - Automatic snapshots on every file change
   - Browse history as virtual directories (`.history/`)
   - Use cases: Document editing, configuration rollback, accidental deletion recovery

3. **Compression Middleware**
   - Transparent zlib/lzma/bz2 compression
   - 3x-10x space savings for text files
   - Use cases: Log files, source code, archival storage

4. **Encryption Middleware**
   - AES-256-GCM transparent encryption
   - Per-file or per-directory encryption
   - Use cases: Sensitive documents, cloud backup, compliance requirements

5. **Full-Text Search Index Middleware**
   - Automatic indexing with inotify monitoring
   - Virtual search interface (`.search/query/...`)
   - Use cases: Document libraries, code search, email archives

6. **Git-Aware Middleware**
   - Auto-commit on every write
   - Browse Git history as filesystem directories
   - Use cases: Automatic versioning, non-Git users, collaborative editing

7. **Cloud Sync Middleware**
   - Transparent sync to S3/Google Drive/Dropbox
   - Local cache with async upload
   - Use cases: Distributed teams, backup, mobile access

8. **Content-Addressed Storage (CAS)**
   - Store files by content hash
   - Natural deduplication at object level
   - Use cases: VM images, container layers, snapshots

9. **Quota & Rate Limiting Middleware**
   - Per-user storage quotas
   - I/O rate limiting
   - Use cases: Multi-tenant systems, resource control

10. **Audit & Compliance Middleware**
    - Log all filesystem operations
    - SIEM integration support
    - Use cases: Security auditing, HIPAA/SOX/GDPR compliance

**Middleware Stacking**: Multiple middleware can be composed in a pipeline for powerful combinations:
- **Backup System**: Dedup → Compress → Encrypt → Cloud Sync
- **Compliance System**: Quota → Audit → Encryption → Rate Limit
- **Development System**: Version → Git Integration → Search Index

**Implementation Priority**:
- Phase 7a (Weeks 13-15): Storage optimization (Dedup, Compression, CAS)
- Phase 7b (Weeks 16-18): Security & compliance (Encryption, Audit, Quota)
- Phase 7c (Weeks 19-22): Advanced features (Versioning, Git, Search, Cloud)

**Reference**: [docs/middleware-ideas.md](docs/middleware-ideas.md)

---

## Configuration Reference

### Basic Configuration

**File**: `config/shadowfs.yaml`

```yaml
shadowfs:
  version: "1.0"

  # Source directories
  sources:
    - path: /data/documents
      priority: 1
      readonly: true

  # Visibility rules
  rules:
    - name: "Hide hidden files"
      type: exclude
      pattern: "**/.*"

    - name: "Show Python files"
      type: include
      pattern: "**/*.py"

  # Content transforms
  transforms:
    - name: "Markdown to HTML"
      pattern: "**/*.md"
      type: convert
      from: markdown
      to: html

  # Virtual layers
  layers:
    - name: by-type
      type: classifier
      classifier: extension

  # Caching
  cache:
    enabled: true
    max_size_mb: 512
    ttl_seconds: 300

  # Logging
  logging:
    level: INFO
    file: /var/log/shadowfs/shadowfs.log
```

**Reference**: [docs/architecture.md § Configuration File Format](docs/architecture.md#configuration-file-format)

---

### Virtual Layer Examples

**Development Environment**:
```yaml
layers:
  - name: by-type
    type: classifier
    classifier: extension

  - name: by-category
    type: classifier
    classifier: pattern
    rules:
      - pattern: "test_*.py"
        category: tests
      - pattern: "*.py"
        category: src
```

**Photo Library**:
```yaml
layers:
  - name: by-date
    type: date
    date_field: ctime

  - name: by-camera
    type: classifier
    classifier: exif
    exif_field: Make
```

**Reference**: [docs/virtual-layers.md § Configuration Format](docs/virtual-layers.md#configuration-format)

---

## Testing Strategy

### Test Structure

```
tests/
├── test_layer1/
│   ├── test_path_utils.py
│   ├── test_file_operations.py
│   └── test_validators.py
│
├── test_layer2/
│   ├── test_config_manager.py
│   ├── test_cache_manager.py
│   └── test_logger.py
│
├── test_layer3/
│   ├── test_rule_engine.py
│   ├── test_transform_pipeline.py
│   └── test_layers/
│       ├── test_classifier_layer.py
│       ├── test_date_layer.py
│       └── test_manager.py
│
├── test_layer4/
│   ├── test_fuse_operations.py
│   └── test_cli.py
│
└── integration/
    ├── test_end_to_end.py
    ├── test_performance.py
    └── test_layers_integration.py
```

### Running Tests

```bash
# All tests
pytest tests/

# Unit tests only
pytest tests/test_layer1/ tests/test_layer2/ tests/test_layer3/

# Integration tests
pytest tests/integration/

# With coverage
pytest --cov=shadowfs tests/

# Performance tests
pytest tests/integration/test_performance.py -v
```

**Reference**: [docs/architecture.md § Testing Strategy](docs/architecture.md#testing-strategy)

---

## Security Considerations

### Security Layers

1. **Path Traversal Prevention**
   - Validate all paths
   - Prevent `../` escapes
   - Resolve symlinks safely

2. **Transform Sandboxing**
   - Restricted execution environment
   - No access to filesystem/network
   - Resource limits (memory, CPU, time)

3. **Permission Enforcement**
   - Respect filesystem ACLs
   - Read-only source restrictions
   - Optional ShadowFS ACLs

4. **Resource Limits**
   - Max file size (1GB default)
   - Max transform time (30s default)
   - Memory limits per operation

5. **Audit Logging**
   - Log security-relevant operations
   - Track access patterns
   - Alert on suspicious activity

**Reference**: [docs/architecture.md § Security Model](docs/architecture.md#security-model)

---

## Performance Optimization

### Caching Strategy

**Three-Level Cache**:
- **L1**: Attributes (stat) - 60s TTL, 10K entries
- **L2**: Content - 300s TTL, 512MB
- **L3**: Transforms - 600s TTL, 1GB

### Async Operations

- Thread pool for I/O operations
- Async file reads
- Background index updates

### Prefetching

- Predict likely accesses
- Preload directory contents
- Cache warming

### Connection Pooling

- Reuse file handles
- Reduce open/close overhead

**Reference**: [docs/architecture.md § Performance Patterns](docs/architecture.md#performance-patterns)

---

## Use Cases

### 1. Development Environment

**Problem**: Build artifacts clutter source directories

**Solution**: Filter view that hides build files
```yaml
rules:
  - name: "Hide build artifacts"
    type: exclude
    patterns:
      - "**/__pycache__/**"
      - "**/node_modules/**"
      - "**/dist/**"
      - "**/build/**"
```

---

### 2. Documentation Site

**Problem**: Need to serve HTML but write in Markdown

**Solution**: Transform Markdown to HTML on-the-fly
```yaml
transforms:
  - name: "MD to HTML"
    pattern: "**/*.md"
    type: convert
    from: markdown
    to: html
    css_theme: github
```

---

### 3. Photo Library Organization

**Problem**: Photos stored flat, want multiple organizational views

**Solution**: Virtual layers by date, camera, tags
```yaml
layers:
  - name: by-date
    type: date
    date_field: ctime

  - name: by-camera
    type: classifier
    classifier: exif

  - name: by-tags
    type: tags
    tag_source: xattr
```

---

### 4. Encrypted Storage

**Problem**: Need transparent encryption/decryption

**Solution**: Transform layer for encryption
```yaml
transforms:
  - name: "Decrypt on read"
    pattern: "**/*.enc"
    type: decrypt
    algorithm: AES-256-GCM
    key_source: env:ENCRYPTION_KEY
```

---

## API Reference

### Command Line Interface

```bash
# Mount filesystem
shadowfs --config CONFIG --mount MOUNTPOINT [options]

# Options:
  --sources PATH [PATH ...]   Source directories
  --config PATH               Configuration file
  --mount PATH                Mount point
  --foreground                Run in foreground (for debugging)
  --debug                     Enable debug logging
  --allow-other               Allow other users to access
  --log-file PATH             Log file location

# Unmount
fusermount -u MOUNTPOINT     # Linux
umount MOUNTPOINT            # macOS
```

### Control API

```bash
# Reload configuration
shadowfs-ctl reload --mount /mnt/shadowfs

# List virtual layers
shadowfs-ctl list-layers --mount /mnt/shadowfs

# Add virtual layer
shadowfs-ctl add-layer by-author \
  --type classifier \
  --classifier git_author \
  --mount /mnt/shadowfs

# Get statistics
shadowfs-ctl stats --mount /mnt/shadowfs
```

---

## Contributing

### Development Setup

```bash
# Clone repository
git clone https://github.com/andronics/shadowfs.git
cd shadowfs

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install in development mode
pip install -e .
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Run linters
flake8 shadowfs/
mypy shadowfs/
black shadowfs/
```

### Coding Standards

- Follow PEP 8 style guide
- Type hints for all functions
- Docstrings for all public APIs
- Unit tests for all components
- Integration tests for workflows

### Pull Request Process

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

**Reference**: [docs/architecture.md § Testing Strategy](docs/architecture.md#testing-strategy)

---

## Architecture Compliance

### Meta-Architecture v1.0.0 Checklist

| Principle | Status | Notes |
|-----------|--------|-------|
| 1. Layered Architecture | ✅ PASS | 4-layer structure implemented |
| 2. Explicit Dependencies | ✅ PASS | requirements.txt, no hidden deps |
| 3. Graceful Degradation | ✅ PASS | Optional transforms, feature flags |
| 4. Input Validation | ✅ PASS | Path validation, config validation |
| 5. Standardized Errors | ✅ PASS | 10 error codes, consistent handling |
| 6. Hierarchical Config | ✅ PASS | 6-level hierarchy with precedence |
| 7. Observable Behavior | ✅ PASS | Logging, metrics, tracing |
| 8. Automated Testing | ✅ PASS | Unit, integration, performance tests |
| 9. Security by Design | ✅ PASS | Path traversal prevention, sandboxing |
| 10. Resource Lifecycle | ✅ PASS | File handle pooling, cleanup |
| 11. Performance Patterns | ✅ PASS | Caching, async ops, prefetching |
| 12. Evolutionary Design | ✅ PASS | Versioned config, feature flags |

**Reference**: [docs/architecture.md § Compliance Matrix](docs/architecture.md#compliance-matrix)

---

## FAQ

### Q: Does ShadowFS copy files?
**A**: No. ShadowFS creates virtual views over existing files. Files remain in their original location. No storage overhead.

### Q: Can I write through ShadowFS?
**A**: Yes, if configured with `readonly: false` for sources. Writes go directly to underlying filesystem. Virtual layers can auto-classify new files.

### Q: How does performance compare to direct access?
**A**:
- **First access**: Slower (rule evaluation, transform, indexing)
- **Cached access**: Near-native (served from memory)
- **Typical overhead**: 5-10% for cached operations

### Q: What happens if config changes?
**A**: Hot-reload without unmounting. Virtual layers rebuild indexes. Cache invalidates affected paths.

### Q: Can I use ShadowFS with remote filesystems?
**A**: Yes. ShadowFS works over any POSIX filesystem including NFS, SMB, sshfs.

### Q: How do I debug issues?
**A**:
1. Mount with `--foreground --debug`
2. Check logs: `/var/log/shadowfs/shadowfs.log`
3. Use control API: `shadowfs-ctl stats`
4. Enable Python profiling

### Q: Is ShadowFS production-ready?
**A**: Currently in design phase. See [Development Roadmap](#development-roadmap) for status.

---

## Related Projects

- **[FUSE](https://github.com/libfuse/libfuse)**: Filesystem in Userspace
- **[fusepy](https://github.com/fusepy/fusepy)**: Python FUSE bindings
- **[UnionFS](https://github.com/rpodgorny/unionfs-fuse)**: Union filesystem (inspiration for view composition)
- **[EncFS](https://github.com/vgough/encfs)**: Encrypted filesystem (inspiration for transforms)
- **[TagFS](https://github.com/marook/tagfs)**: Tag-based filesystem (inspiration for virtual layers)
- **[DedupFS](https://github.com/xolox/dedupfs)**: Deduplication filesystem (inspiration for middleware)
- **[gitfs](https://github.com/presslabs/gitfs)**: Git-integrated filesystem (inspiration for middleware)

---

## License

MIT License - See LICENSE file for details

---

## Contact

**Project Maintainer**: Stephen Cox (andronics)

**Documentation**:
- Architecture: [docs/architecture.md](docs/architecture.md)
- Virtual Layers: [docs/virtual-layers.md](docs/virtual-layers.md)
- Middleware Extensions: [docs/middleware-ideas.md](docs/middleware-ideas.md)
- Conceptual Foundation: [docs/typescript-type-discovery.md](docs/typescript-type-discovery.md)

**Repository**: https://github.com/andronics/shadowfs

---

## Document Status

**Version**: 1.1.0
**Last Updated**: 2025-11-11
**Status**: Design Phase (with Phase 7 middleware roadmap added)
**Next Review**: Upon completion of Phase 1 (Foundation)

### Document Maintenance

#### CLAUDE.md Updates

This file should be updated when:
- [ ] New documentation is added
- [ ] Architecture changes occur
- [ ] Development phases complete
- [ ] Configuration format changes
- [ ] New components are added
- [ ] API changes occur

#### PLAN.md Updates - CRITICAL

**PLAN.md is the authoritative implementation guide and MUST be kept current:**

**When to Update PLAN.md:**
- [ ] **Phase Completion**: Mark tasks complete, update status, document completion date
- [ ] **Timeline Changes**: Update estimates if phases take longer/shorter than planned
- [ ] **Scope Changes**: Document any additions or removals from original plan
- [ ] **Blockers Found**: Add to risk mitigation section
- [ ] **Lessons Learned**: Add insights that would help future phases
- [ ] **Test Coverage**: Update actual coverage percentages achieved
- [ ] **Performance Metrics**: Record actual vs. target performance

**How to Update PLAN.md:**
1. Mark completed tasks with `[x]` in checklists
2. Update phase status (Not Started → In Progress → Complete)
3. Add completion dates next to phase headers
4. Document any deviations from original plan with rationale
5. Update risk mitigation based on actual issues encountered
6. Keep success metrics current with actual measurements

**Review Schedule**:
- Daily during active development (quick status check)
- Weekly for comprehensive review and updates
- At each phase boundary for detailed documentation

---

*This document provides a comprehensive overview of the ShadowFS project. For detailed technical specifications, refer to the linked documentation files. For implementation details and current status, always consult [PLAN.md](PLAN.md).*
