# ShadowFS

**Dynamic Filesystem Transformation Layer**

A FUSE-based filesystem that provides dynamic filtering, on-the-fly content transformation, and virtual organizational views over existing filesystems—all without copying files or consuming additional storage.

[![Tests](https://img.shields.io/badge/tests-187%20passing-success)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-97%25-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## Overview

ShadowFS creates a "shadow layer" over your existing filesystems, enabling:

- **Dynamic Filtering**: Show/hide files based on runtime-configurable rules
- **On-the-Fly Transformation**: Convert, compress, encrypt, or template files transparently during read
- **Virtual Organization**: Create multiple directory structures (by type, date, tags) over the same files
- **Zero Storage Overhead**: Files remain in place—no copying, no duplication

Think of it as "virtual filesystem middleware" that sits between applications and your files, providing programmable views and transformations.

## Quick Start

```bash
# Install dependencies
pip install fusepy pyyaml jinja2

# Clone and install
git clone https://github.com/andronics/shadowfs.git
cd shadowfs
pip install -e .

# Run tests
pytest tests/ -v

# Mount with configuration
shadowfs --config shadowfs.yaml --mount /mnt/shadowfs
```

## Example Use Cases

### 1. Clean Development View
Hide build artifacts and clutter:
```yaml
rules:
  - name: "Hide build files"
    type: exclude
    patterns:
      - "**/__pycache__/**"
      - "**/node_modules/**"
      - "**/dist/**"
```

### 2. Auto-Convert Documentation
Read Markdown as HTML on-the-fly:
```yaml
transforms:
  - name: "Markdown to HTML"
    pattern: "**/*.md"
    type: convert
    from: markdown
    to: html
```

### 3. Multi-View Photo Library
Organize by date, camera, tags simultaneously:
```yaml
virtual_layers:
  - name: by-date
    type: date
    date_field: ctime
  - name: by-camera
    type: classifier
    classifier: exif
```

## Project Status

**Current Phase**: Phase 3 Complete (Integration - Transforms)

- ✅ **Phase 0**: Development Infrastructure
- ✅ **Phase 1**: Foundation Layer (path utilities, file operations, validators)
- ✅ **Phase 2**: Infrastructure Layer (config, cache, logging, metrics)
- ✅ **Phase 3**: Integration - Transforms (compression, format conversion, templates)
- 🚧 **Phase 4**: Integration - Virtual Layers (in progress)
- ⏳ **Phase 5**: Application Layer (FUSE operations)
- ⏳ **Phase 6**: Production Readiness

**Test Coverage**: 187 tests passing with ~97% average coverage on completed phases.

## Architecture

ShadowFS follows a **4-layer architecture** compliant with Meta-Architecture v1.0.0:

```
┌─────────────────────────────────────────┐
│   Layer 4: Application                   │
│   (FUSE operations, CLI, control API)    │
├─────────────────────────────────────────┤
│   Layer 3: Integration                   │
│   (transforms, rules, virtual layers)    │
├─────────────────────────────────────────┤
│   Layer 2: Infrastructure                │
│   (config, cache, logging, metrics)      │
├─────────────────────────────────────────┤
│   Layer 1: Foundation                    │
│   (path utils, file ops, validators)     │
└─────────────────────────────────────────┘
```

**Key Components**:
- **Transform Pipeline**: Chain multiple transforms (compression → encryption → conversion)
- **Rule Engine**: Pattern-based file visibility control
- **Virtual Layers**: Multiple organizational views over same files
- **Multi-Level Caching**: 3-tier cache (attributes, content, transforms)

## Configuration Example

```yaml
shadowfs:
  version: "1.0"

  sources:
    - path: /data/documents
      priority: 1
      readonly: true

  rules:
    - name: "Hide hidden files"
      type: exclude
      pattern: "**/.*"

  transforms:
    - name: "Auto-decompress"
      pattern: "**/*.gz"
      type: decompress
      algorithm: gzip

  virtual_layers:
    - name: by-type
      type: classifier
      classifier: extension

  cache:
    enabled: true
    max_size_mb: 512
    ttl_seconds: 300
```

## Features

### Transforms
- **Compression**: gzip, bz2, lzma (compress/decompress)
- **Format Conversion**: Markdown→HTML, CSV↔JSON, YAML→JSON
- **Templates**: Jinja2 template rendering with context
- **Extensible**: Plugin architecture for custom transforms

### Virtual Layers
- **Classifier**: Organize by extension, size, MIME type
- **Date-based**: Hierarchical date structures (YYYY/MM/DD)
- **Tag-based**: Organize by metadata tags
- **Pattern-based**: Rule-driven classification

### Performance
- **3-tier caching**: Attributes (60s), Content (300s), Transforms (600s)
- **Async operations**: Thread pool for I/O
- **Lazy evaluation**: Transforms only applied when accessed
- **Connection pooling**: Reuse file handles

## Documentation

- **[CLAUDE.md](CLAUDE.md)**: Complete project documentation
- **[PLAN.md](PLAN.md)**: Implementation roadmap and progress
- **[docs/architecture.md](docs/architecture.md)**: Technical architecture (Meta-Architecture v1.0.0 compliant)
- **[docs/virtual-layers.md](docs/virtual-layers.md)**: Virtual layer system design
- **[docs/middleware-ideas.md](docs/middleware-ideas.md)**: Future middleware extensions
- **[docs/typescript-type-discovery.md](docs/typescript-type-discovery.md)**: Conceptual foundation

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=shadowfs --cov-report=html

# Run specific test suite
pytest tests/transforms/ -v
pytest tests/integration/ -v

# Run with specific coverage target
pytest tests/transforms/ --cov=shadowfs/transforms --cov-report=term-missing
```

**Current Test Stats**:
- Foundation tests: Coming in Phase 1 completion
- Infrastructure tests: Coming in Phase 2 completion
- Transform tests: 120 tests, ~97% coverage
- Pipeline tests: 34 tests, 99.37% coverage
- Base transform tests: 33 tests, 98.82% coverage

## Development

### Requirements
- Python 3.11+
- FUSE (libfuse3-dev on Debian/Ubuntu)
- Optional: markdown, pyyaml, jinja2 (for specific transforms)

### Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -e .
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/ -v
```

### Code Quality
- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **pytest**: 100% coverage target
- **pre-commit**: Automated checks

## Inspiration

The "shadow filesystem" concept was inspired by TypeScript's `.d.ts` type discovery system—just as TypeScript creates a type layer over JavaScript, ShadowFS creates organizational and transformation layers over filesystems.

## Related Projects

- **[FUSE](https://github.com/libfuse/libfuse)**: Filesystem in Userspace
- **[fusepy](https://github.com/fusepy/fusepy)**: Python FUSE bindings
- **[UnionFS](https://github.com/rpodgorny/unionfs-fuse)**: Union filesystem (view composition inspiration)
- **[EncFS](https://github.com/vgough/encfs)**: Encrypted filesystem (transform inspiration)
- **[TagFS](https://github.com/marook/tagfs)**: Tag-based filesystem (virtual layer inspiration)

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass with good coverage
5. Follow code quality standards (black, isort, flake8, mypy)
6. Submit a pull request

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Contact

**Project Maintainer**: Stephen Cox (andronics)

**Repository**: https://github.com/andronics/shadowfs

---

**Status**: Design & Implementation Phase
**Version**: 0.1.0-alpha
**Last Updated**: 2025-11-11
