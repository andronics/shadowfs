# Virtual Layers: Dynamic Directory Structure Generation

**Extension to ShadowFS Architecture v1.0**

*Creating multiple organizational views of the same files through configurable virtual directory hierarchies*

---

## The Core Mechanism

### What's Actually Happening?

Virtual Layers are **middleware components** that intercept path resolution and create synthetic directory structures. The mechanism works through:

1. **Path Interception**: When a path is accessed through ShadowFS:
   - Check if path starts with a virtual layer prefix (e.g., `/by-type/`)
   - If yes, route through virtual layer path resolver
   - If no, pass through to standard path resolution

2. **Virtual Path Resolution**: Virtual layer translates synthetic path to real file:
   ```
   Virtual: /by-type/python/project1.py
   ↓ (Layer: "by-type", Classifier: file extension)
   Real: /source/project1.py
   ```

3. **Reverse Index**: Virtual layers maintain a mapping:
   ```
   Classifier → Classification → Files
   
   "by-type":
     "python" → [project1.py, project2.py, test_project1.py]
     "docs" → [README.md]
   
   "by-category":
     "projects" → [project1.py, project2.py]
     "tests" → [test_project1.py]
     "docs" → [README.md]
   ```

4. **Dynamic Index Updates**: Index rebuilds when:
   - Files are added/removed/modified in source
   - Configuration changes
   - Metadata changes (tags, attributes)

**Key Insight**: Virtual layers are **saved queries materialized as directory structures**. Each directory in a virtual layer represents a predicate that files match.

---

## Architecture Integration

### Extended ShadowFS Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│          (ls, cat, grep, your-app, etc.)                    │
└─────────────────────────────────┬───────────────────────────┘
                                  │
                      ╔═══════════▼═══════════╗
                      ║    FUSE Kernel        ║
                      ╚═══════════╤═══════════╝
                                  │
┌─────────────────────────────────▼───────────────────────────┐
│                   ShadowFS (Python)                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Layer 4: FUSE Operations Handler                     │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────▼─────────────────────────────────┐  │
│  │  NEW: Virtual Layer Router                            │  │
│  │   ┌────────────┬────────────┬─────────────┐          │  │
│  │   │ by-type    │ by-date    │ by-tags     │          │  │
│  │   └────────────┴────────────┴─────────────┘          │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────▼─────────────────────────────────┐  │
│  │  Layer 3: Rule Engine + Transform Pipeline            │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────▼─────────────────────────────────┐  │
│  │  Layer 2: Config, Cache, Logging                      │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────▼─────────────────────────────────┐  │
│  │  Layer 1: Path Utils, File Ops                        │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────┬───────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────┐
│              Underlying Filesystem(s)                        │
└─────────────────────────────────────────────────────────────┘
```

### Virtual Layer Router (New Component)

```python
class VirtualLayerRouter:
    """
    Routes paths through virtual layers or to real filesystem.
    
    Sits between FUSE operations and rule engine.
    """
    
    def __init__(self, layers: List[VirtualLayer], sources: List[str]):
        self.layers = {layer.name: layer for layer in layers}
        self.sources = sources
        
    def resolve_path(self, virtual_path: str) -> Optional[str]:
        """
        Resolve virtual path to real path.
        
        Returns:
            Real path if virtual layer active, None if pass-through
        """
        parts = virtual_path.strip('/').split('/', 1)
        
        if not parts:
            return None
        
        layer_name = parts[0]
        
        # Check if this is a virtual layer
        if layer_name in self.layers:
            layer = self.layers[layer_name]
            
            if len(parts) == 1:
                # Just the layer root - list categories
                return None  # Special case: virtual directory listing
            
            # Resolve through virtual layer
            return layer.resolve(parts[1])
        
        # Not a virtual layer - pass through
        return None
    
    def list_virtual_root(self) -> List[str]:
        """List all available virtual layers at mount root"""
        return list(self.layers.keys())
    
    def list_virtual_directory(self, layer_name: str, subpath: str = "") -> List[str]:
        """List contents of virtual directory"""
        if layer_name not in self.layers:
            raise FileNotFoundError(f"Virtual layer not found: {layer_name}")
        
        layer = self.layers[layer_name]
        return layer.list_directory(subpath)
```

---

## Virtual Layer Types

### 1. Classifier-Based Layers

**Group files by some property (extension, size, date, etc.)**

```python
class ClassifierLayer(VirtualLayer):
    """
    Virtual layer that classifies files by a property.
    
    Example: by-type, by-size, by-date
    """
    
    def __init__(self, name: str, classifier: Callable[[FileInfo], str]):
        self.name = name
        self.classifier = classifier
        self.index = {}  # category → [files]
        
    def build_index(self, files: List[FileInfo]):
        """Build reverse index: category → files"""
        self.index.clear()
        
        for file in files:
            category = self.classifier(file)
            if category not in self.index:
                self.index[category] = []
            self.index[category].append(file)
    
    def resolve(self, virtual_path: str) -> Optional[str]:
        """
        Resolve virtual path to real path.
        
        Virtual: python/project1.py
        Real: /source/project1.py
        """
        parts = virtual_path.split('/', 1)
        
        if len(parts) != 2:
            return None
        
        category, filename = parts
        
        if category not in self.index:
            return None
        
        # Find file in this category
        for file in self.index[category]:
            if file.name == filename:
                return file.real_path
        
        return None
    
    def list_directory(self, subpath: str = "") -> List[str]:
        """
        List virtual directory contents.
        
        subpath="" → list categories
        subpath="python" → list files in python category
        """
        if not subpath:
            # List categories
            return sorted(self.index.keys())
        
        # List files in category
        category = subpath.rstrip('/')
        if category in self.index:
            return sorted([f.name for f in self.index[category]])
        
        return []
```

### 2. Tag-Based Layers

**Organize by metadata tags**

```python
class TagLayer(VirtualLayer):
    """
    Virtual layer that organizes files by tags.
    
    Example: by-tags/important/, by-tags/work/
    """
    
    def __init__(self, name: str, tag_extractor: Callable[[FileInfo], List[str]]):
        self.name = name
        self.tag_extractor = tag_extractor
        self.index = {}  # tag → [files]
    
    def build_index(self, files: List[FileInfo]):
        """Build index: tags → files"""
        self.index.clear()
        
        for file in files:
            tags = self.tag_extractor(file)
            for tag in tags:
                if tag not in self.index:
                    self.index[tag] = []
                self.index[tag].append(file)
    
    def resolve(self, virtual_path: str) -> Optional[str]:
        """
        Resolve tag-based path.
        
        Virtual: important/project1.py
        Real: /source/project1.py
        """
        parts = virtual_path.split('/', 1)
        
        if len(parts) != 2:
            return None
        
        tag, filename = parts
        
        if tag not in self.index:
            return None
        
        for file in self.index[tag]:
            if file.name == filename:
                return file.real_path
        
        return None
    
    def list_directory(self, subpath: str = "") -> List[str]:
        """List tags or files in tag"""
        if not subpath:
            return sorted(self.index.keys())
        
        tag = subpath.rstrip('/')
        if tag in self.index:
            return sorted([f.name for f in self.index[tag]])
        
        return []
```

### 3. Hierarchical Query Layers

**Multi-level directory hierarchies based on multiple properties**

```python
class HierarchicalLayer(VirtualLayer):
    """
    Virtual layer with multi-level hierarchy.
    
    Example: by-project/projectA/src/
             by-project/projectA/tests/
             by-project/projectB/src/
    """
    
    def __init__(self, name: str, hierarchy: List[Callable[[FileInfo], str]]):
        self.name = name
        self.hierarchy = hierarchy  # List of classifiers for each level
        self.index = {}  # nested dict: level1 → level2 → ... → [files]
    
    def build_index(self, files: List[FileInfo]):
        """Build nested index"""
        self.index.clear()
        
        for file in files:
            # Classify at each level
            path_parts = [classifier(file) for classifier in self.hierarchy]
            
            # Build nested structure
            current = self.index
            for part in path_parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Last level stores files
            last_part = path_parts[-1]
            if last_part not in current:
                current[last_part] = []
            current[last_part].append(file)
    
    def resolve(self, virtual_path: str) -> Optional[str]:
        """Resolve multi-level path"""
        parts = virtual_path.split('/')
        
        if len(parts) < len(self.hierarchy) + 1:
            return None
        
        # Navigate hierarchy
        current = self.index
        for part in parts[:len(self.hierarchy)]:
            if part not in current:
                return None
            current = current[part]
        
        # Last part is filename
        filename = parts[len(self.hierarchy)]
        
        if isinstance(current, list):
            for file in current:
                if file.name == filename:
                    return file.real_path
        
        return None
    
    def list_directory(self, subpath: str = "") -> List[str]:
        """List directory at any level of hierarchy"""
        if not subpath:
            return sorted(self.index.keys())
        
        parts = subpath.rstrip('/').split('/')
        current = self.index
        
        for part in parts:
            if part not in current:
                return []
            current = current[part]
        
        if isinstance(current, dict):
            return sorted(current.keys())
        elif isinstance(current, list):
            return sorted([f.name for f in current])
        
        return []
```

### 4. Date-Based Layers

**Organize by time (year/month/day hierarchy)**

```python
class DateLayer(VirtualLayer):
    """
    Virtual layer organized by date.
    
    Example: by-date/2024/11/11/project1.py
             by-date/2024/11/10/oldfile.py
    """
    
    def __init__(self, name: str, date_field: str = "mtime"):
        self.name = name
        self.date_field = date_field  # mtime, ctime, or atime
        self.index = {}  # year → month → day → [files]
    
    def build_index(self, files: List[FileInfo]):
        """Build date hierarchy index"""
        self.index.clear()
        
        for file in files:
            timestamp = getattr(file, self.date_field)
            dt = datetime.fromtimestamp(timestamp)
            
            year = str(dt.year)
            month = f"{dt.month:02d}"
            day = f"{dt.day:02d}"
            
            # Build nested structure
            if year not in self.index:
                self.index[year] = {}
            if month not in self.index[year]:
                self.index[year][month] = {}
            if day not in self.index[year][month]:
                self.index[year][month][day] = []
            
            self.index[year][month][day].append(file)
    
    def resolve(self, virtual_path: str) -> Optional[str]:
        """Resolve date-based path"""
        parts = virtual_path.split('/')
        
        if len(parts) != 4:  # year/month/day/filename
            return None
        
        year, month, day, filename = parts
        
        if year not in self.index:
            return None
        if month not in self.index[year]:
            return None
        if day not in self.index[year][month]:
            return None
        
        files = self.index[year][month][day]
        for file in files:
            if file.name == filename:
                return file.real_path
        
        return None
    
    def list_directory(self, subpath: str = "") -> List[str]:
        """List year/month/day hierarchy"""
        if not subpath:
            return sorted(self.index.keys())
        
        parts = subpath.rstrip('/').split('/')
        current = self.index
        
        for part in parts:
            if part not in current:
                return []
            current = current[part]
        
        if isinstance(current, dict):
            return sorted(current.keys())
        elif isinstance(current, list):
            return sorted([f.name for f in current])
        
        return []
```

---

## Configuration Format

### Virtual Layer Configuration

```yaml
# shadowfs.yaml
shadowfs:
  sources:
    - path: /source/documents
      priority: 1
  
  # Virtual layer definitions
  virtual_layers:
    
    # Simple classifier layer: by file extension
    - name: by-type
      type: classifier
      classifier: extension
      mappings:
        ".py": python
        ".js": javascript
        ".md": docs
        ".txt": docs
        ".go": go
        ".rs": rust
      default_category: other
    
    # Tag-based layer: by metadata tags
    - name: by-tags
      type: tags
      tag_source: xattr  # Extended attributes
      tag_attribute: user.tags
      separator: ","
    
    # Size-based classifier
    - name: by-size
      type: classifier
      classifier: size
      ranges:
        - name: tiny
          max: 1KB
        - name: small
          max: 100KB
        - name: medium
          max: 10MB
        - name: large
          max: 1GB
        - name: huge
          min: 1GB
    
    # Date-based hierarchy
    - name: by-date
      type: date
      date_field: mtime  # or ctime, atime
      format: YYYY/MM/DD
    
    # Pattern-based classification
    - name: by-category
      type: classifier
      classifier: pattern
      rules:
        - pattern: "test_*.py"
          category: tests
        - pattern: "*_test.py"
          category: tests
        - pattern: "*.py"
          category: projects
          condition: "not filename.startswith('test')"
        - pattern: "README*"
          category: docs
        - pattern: "*.md"
          category: docs
    
    # Multi-level hierarchy: project → type
    - name: by-project
      type: hierarchical
      levels:
        - classifier: project  # Custom extractor
          extractor: |
            # Python code to extract project name
            path_parts = file.path.split('/')
            return path_parts[0] if path_parts else 'unknown'
        
        - classifier: type
          extractor: |
            ext = file.extension
            if ext == '.py':
              if file.name.startswith('test_'):
                return 'tests'
              else:
                return 'src'
            elif ext in ['.md', '.txt']:
              return 'docs'
            else:
              return 'other'
    
    # Advanced: Git-based organization
    - name: by-git-status
      type: classifier
      classifier: git_status
      enabled_if: "git_available"
      categories:
        - untracked
        - modified
        - staged
        - committed
    
    # Advanced: MIME type classification
    - name: by-mimetype
      type: classifier
      classifier: mimetype
      categories:
        text: ["text/plain", "text/markdown", "text/html"]
        code: ["text/x-python", "text/x-java", "application/javascript"]
        images: ["image/*"]
        documents: ["application/pdf", "application/msword"]
        archives: ["application/zip", "application/x-tar"]
```

### Built-in Classifiers

```python
class BuiltinClassifiers:
    """Built-in classifier functions"""
    
    @staticmethod
    def extension(file: FileInfo) -> str:
        """Classify by file extension"""
        return file.extension.lstrip('.')
    
    @staticmethod
    def size(file: FileInfo, ranges: List[Dict]) -> str:
        """Classify by file size"""
        size = file.size
        
        for range_def in ranges:
            min_size = range_def.get('min', 0)
            max_size = range_def.get('max', float('inf'))
            
            if min_size <= size < max_size:
                return range_def['name']
        
        return 'unknown'
    
    @staticmethod
    def pattern(file: FileInfo, rules: List[Dict]) -> str:
        """Classify by pattern matching"""
        for rule in rules:
            pattern = rule['pattern']
            category = rule['category']
            condition = rule.get('condition')
            
            if fnmatch.fnmatch(file.name, pattern):
                # Check optional condition
                if condition:
                    if eval_safe_condition(condition, {'file': file, 'filename': file.name}):
                        return category
                else:
                    return category
        
        return 'other'
    
    @staticmethod
    def mimetype(file: FileInfo) -> str:
        """Classify by MIME type"""
        import mimetypes
        mimetype, _ = mimetypes.guess_type(file.path)
        return mimetype or 'unknown'
    
    @staticmethod
    def git_status(file: FileInfo) -> str:
        """Classify by Git status"""
        import subprocess
        
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain', file.path],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            status_code = result.stdout[:2] if result.stdout else ''
            
            if not status_code:
                return 'committed'
            elif status_code.strip() == '??':
                return 'untracked'
            elif status_code[0] != ' ':
                return 'staged'
            elif status_code[1] != ' ':
                return 'modified'
            
        except Exception:
            pass
        
        return 'unknown'
```

---

## Implementation

### VirtualLayer Base Class

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Callable
from dataclasses import dataclass
import os

@dataclass
class FileInfo:
    """File information for classification"""
    name: str
    path: str
    real_path: str
    extension: str
    size: int
    mtime: float
    ctime: float
    atime: float
    
    @classmethod
    def from_path(cls, real_path: str, virtual_root: str = "") -> 'FileInfo':
        """Create FileInfo from real path"""
        stat = os.stat(real_path)
        name = os.path.basename(real_path)
        _, ext = os.path.splitext(name)
        
        # Virtual path relative to sources
        path = real_path
        if virtual_root:
            path = os.path.relpath(real_path, virtual_root)
        
        return cls(
            name=name,
            path=path,
            real_path=real_path,
            extension=ext,
            size=stat.st_size,
            mtime=stat.st_mtime,
            ctime=stat.st_ctime,
            atime=stat.st_atime
        )


class VirtualLayer(ABC):
    """Base class for virtual layers"""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def build_index(self, files: List[FileInfo]):
        """Build the virtual layer index from source files"""
        pass
    
    @abstractmethod
    def resolve(self, virtual_path: str) -> Optional[str]:
        """Resolve virtual path to real path"""
        pass
    
    @abstractmethod
    def list_directory(self, subpath: str = "") -> List[str]:
        """List contents of virtual directory"""
        pass
    
    def refresh(self, files: List[FileInfo]):
        """Rebuild index (called on file changes)"""
        self.build_index(files)
```

### Virtual Layer Manager

```python
class VirtualLayerManager:
    """Manages all virtual layers and coordinates index updates"""
    
    def __init__(self, sources: List[str]):
        self.sources = sources
        self.layers = {}
        self.file_index = []  # All files from sources
        self.dirty = True
    
    def add_layer(self, layer: VirtualLayer):
        """Add a virtual layer"""
        self.layers[layer.name] = layer
        self.dirty = True
    
    def remove_layer(self, name: str):
        """Remove a virtual layer"""
        if name in self.layers:
            del self.layers[name]
    
    def scan_sources(self):
        """Scan all source directories and build file index"""
        self.file_index.clear()
        
        for source in self.sources:
            for root, dirs, files in os.walk(source):
                for filename in files:
                    real_path = os.path.join(root, filename)
                    file_info = FileInfo.from_path(real_path, source)
                    self.file_index.append(file_info)
        
        self.dirty = True
    
    def rebuild_indexes(self):
        """Rebuild all virtual layer indexes"""
        if not self.dirty:
            return
        
        for layer in self.layers.values():
            layer.build_index(self.file_index)
        
        self.dirty = False
    
    def resolve_path(self, virtual_path: str) -> Optional[str]:
        """Resolve virtual path through appropriate layer"""
        parts = virtual_path.strip('/').split('/', 1)
        
        if not parts:
            return None
        
        layer_name = parts[0]
        
        if layer_name not in self.layers:
            return None
        
        if len(parts) == 1:
            # Just the layer root
            return None
        
        layer = self.layers[layer_name]
        return layer.resolve(parts[1])
    
    def list_layers(self) -> List[str]:
        """List all available virtual layers"""
        return list(self.layers.keys())
    
    def list_directory(self, virtual_path: str) -> List[str]:
        """List contents of virtual directory"""
        parts = virtual_path.strip('/').split('/', 1)
        
        if not parts or not parts[0]:
            # Root: list all layers
            return self.list_layers()
        
        layer_name = parts[0]
        
        if layer_name not in self.layers:
            raise FileNotFoundError(f"Layer not found: {layer_name}")
        
        layer = self.layers[layer_name]
        subpath = parts[1] if len(parts) > 1 else ""
        
        return layer.list_directory(subpath)
    
    def watch_sources(self):
        """Watch source directories for changes and trigger refresh"""
        # Use inotify/FSEvents to watch for file changes
        # When files change, set self.dirty = True
        # Background thread periodically calls rebuild_indexes()
        pass
```

---

## FUSE Integration

### Modified FUSE Operations

```python
class ShadowFS(Operations):
    """FUSE operations with virtual layer support"""
    
    def __init__(self, sources: List[str], config: Config):
        self.sources = sources
        self.config = config
        
        # Initialize virtual layer manager
        self.vl_manager = VirtualLayerManager(sources)
        self._setup_virtual_layers()
        
        # Initial scan and index build
        self.vl_manager.scan_sources()
        self.vl_manager.rebuild_indexes()
    
    def _setup_virtual_layers(self):
        """Create virtual layers from configuration"""
        for layer_config in self.config.virtual_layers:
            layer = create_layer_from_config(layer_config)
            self.vl_manager.add_layer(layer)
    
    def getattr(self, path: str, fh=None) -> Dict:
        """Get file attributes (handles virtual and real paths)"""
        # Try virtual layer resolution first
        real_path = self.vl_manager.resolve_path(path)
        
        if real_path:
            # Virtual path resolved to real file
            return get_file_attributes(real_path)
        
        # Check if this is a virtual directory
        if self._is_virtual_directory(path):
            # Return directory attributes
            return {
                'st_mode': stat.S_IFDIR | 0o755,
                'st_nlink': 2,
                'st_size': 4096,
                'st_ctime': time.time(),
                'st_mtime': time.time(),
                'st_atime': time.time(),
            }
        
        # Not a virtual path - try standard resolution
        return self._getattr_standard(path, fh)
    
    def readdir(self, path: str, fh) -> List[str]:
        """List directory (handles virtual and real directories)"""
        # Check if this is virtual layer directory
        if self._is_virtual_path(path):
            try:
                entries = self.vl_manager.list_directory(path)
                return ['.', '..'] + entries
            except FileNotFoundError:
                raise FuseOSError(errno.ENOENT)
        
        # Standard directory listing
        return self._readdir_standard(path, fh)
    
    def open(self, path: str, flags: int) -> int:
        """Open file (resolve virtual path to real)"""
        # Resolve virtual path
        real_path = self.vl_manager.resolve_path(path)
        
        if real_path:
            # Virtual file - open real file
            return self._open_real(real_path, flags)
        
        # Standard open
        return self._open_standard(path, flags)
    
    def read(self, path: str, size: int, offset: int, fh: int) -> bytes:
        """Read file (already opened, fh points to real file)"""
        # File handle already points to real file
        # Just read from it
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, size)
    
    def _is_virtual_path(self, path: str) -> bool:
        """Check if path is within a virtual layer"""
        parts = path.strip('/').split('/', 1)
        if not parts:
            return False
        return parts[0] in self.vl_manager.list_layers()
    
    def _is_virtual_directory(self, path: str) -> bool:
        """Check if path is a virtual directory"""
        if not path or path == '/':
            return True  # Root always virtual
        
        try:
            entries = self.vl_manager.list_directory(path)
            return True  # Successfully listed - it's a directory
        except FileNotFoundError:
            return False
```

---

## Usage Examples

### Example 1: Development Environment

**Configuration:**
```yaml
virtual_layers:
  - name: by-type
    type: classifier
    classifier: extension
    mappings:
      ".py": python
      ".js": javascript
      ".go": go
      ".md": docs
      ".txt": docs
  
  - name: by-category
    type: classifier
    classifier: pattern
    rules:
      - pattern: "test_*.py"
        category: tests
      - pattern: "*_test.py"
        category: tests
      - pattern: "*.py"
        category: projects
      - pattern: "README*"
        category: docs
```

**Result:**
```bash
$ tree /mnt/shadowfs/
/mnt/shadowfs/
├── by-type/
│   ├── python/
│   │   ├── project1.py
│   │   ├── project2.py
│   │   └── test_project1.py
│   ├── javascript/
│   │   └── app.js
│   └── docs/
│       ├── README.md
│       └── notes.txt
└── by-category/
    ├── projects/
    │   ├── project1.py
    │   └── project2.py
    ├── tests/
    │   └── test_project1.py
    └── docs/
        ├── README.md
        └── notes.txt

$ cat /mnt/shadowfs/by-type/python/project1.py
# Same content as /source/project1.py

$ cat /mnt/shadowfs/by-category/projects/project1.py
# Same content as /source/project1.py
```

### Example 2: Photo Library

**Configuration:**
```yaml
sources:
  - path: /photos/raw

virtual_layers:
  - name: by-date
    type: date
    date_field: ctime  # Creation time
    format: YYYY/MM/DD
  
  - name: by-camera
    type: classifier
    classifier: exif
    exif_field: Make
    default_category: unknown
  
  - name: by-tags
    type: tags
    tag_source: xattr
    tag_attribute: user.tags
```

**Result:**
```bash
$ tree /mnt/shadowfs/by-date/2024/11/
/mnt/shadowfs/by-date/2024/11/
├── 10/
│   ├── IMG_001.jpg
│   └── IMG_002.jpg
└── 11/
    └── IMG_003.jpg

$ tree /mnt/shadowfs/by-camera/
/mnt/shadowfs/by-camera/
├── Canon/
│   └── IMG_001.jpg
├── Nikon/
│   └── IMG_002.jpg
└── Sony/
    └── IMG_003.jpg

$ tree /mnt/shadowfs/by-tags/
/mnt/shadowfs/by-tags/
├── vacation/
│   ├── IMG_001.jpg
│   └── IMG_003.jpg
└── family/
    ├── IMG_002.jpg
    └── IMG_003.jpg
```

### Example 3: Code Repository

**Configuration:**
```yaml
virtual_layers:
  - name: by-project
    type: hierarchical
    levels:
      - classifier: project
        extractor: |
          parts = file.path.split('/')
          return parts[0] if len(parts) > 0 else 'unknown'
      
      - classifier: type
        extractor: |
          if file.name.startswith('test_'):
            return 'tests'
          elif file.extension == '.py':
            return 'src'
          elif file.extension in ['.md', '.txt']:
            return 'docs'
          else:
            return 'other'
  
  - name: by-git-status
    type: classifier
    classifier: git_status
    categories:
      - untracked
      - modified
      - staged
      - committed
```

**Result:**
```bash
$ tree /mnt/shadowfs/by-project/
/mnt/shadowfs/by-project/
├── projectA/
│   ├── src/
│   │   ├── main.py
│   │   └── utils.py
│   ├── tests/
│   │   └── test_main.py
│   └── docs/
│       └── README.md
└── projectB/
    ├── src/
    │   └── app.py
    └── tests/
        └── test_app.py

$ tree /mnt/shadowfs/by-git-status/
/mnt/shadowfs/by-git-status/
├── modified/
│   └── main.py
├── staged/
│   └── utils.py
└── committed/
    ├── app.py
    ├── test_main.py
    └── README.md
```

---

## Performance Considerations

### Index Building

**Problem**: Scanning large directories is expensive

**Solutions**:
1. **Incremental Updates**: Only rebuild index for changed files
2. **Lazy Loading**: Build index on-demand, not at startup
3. **Background Indexing**: Scan in background thread
4. **Caching**: Cache index to disk, reload on startup

```python
class IncrementalIndexBuilder:
    """Build index incrementally as files change"""
    
    def __init__(self, vl_manager: VirtualLayerManager):
        self.vl_manager = vl_manager
        self.file_cache = {}  # path → FileInfo
    
    def on_file_created(self, path: str):
        """Handle new file"""
        file_info = FileInfo.from_path(path)
        self.file_cache[path] = file_info
        
        # Update only affected layers
        for layer in self.vl_manager.layers.values():
            layer.add_file(file_info)
    
    def on_file_deleted(self, path: str):
        """Handle file deletion"""
        if path in self.file_cache:
            file_info = self.file_cache[path]
            del self.file_cache[path]
            
            # Update layers
            for layer in self.vl_manager.layers.values():
                layer.remove_file(file_info)
    
    def on_file_modified(self, path: str):
        """Handle file modification"""
        # Remove old version
        self.on_file_deleted(path)
        # Add new version
        self.on_file_created(path)
```

### Path Resolution

**Problem**: Resolving virtual paths repeatedly is expensive

**Solution**: Cache resolved paths

```python
class PathCache:
    """Cache virtual → real path mappings"""
    
    def __init__(self, ttl: int = 60):
        self.cache = {}  # virtual_path → (real_path, timestamp)
        self.ttl = ttl
    
    def get(self, virtual_path: str) -> Optional[str]:
        """Get cached real path"""
        if virtual_path not in self.cache:
            return None
        
        real_path, timestamp = self.cache[virtual_path]
        
        # Check TTL
        if time.time() - timestamp > self.ttl:
            del self.cache[virtual_path]
            return None
        
        return real_path
    
    def set(self, virtual_path: str, real_path: str):
        """Cache path mapping"""
        self.cache[virtual_path] = (real_path, time.time())
    
    def invalidate(self, pattern: str = None):
        """Invalidate cached paths"""
        if pattern is None:
            # Invalidate all
            self.cache.clear()
        else:
            # Invalidate matching pattern
            keys_to_remove = [
                k for k in self.cache.keys()
                if fnmatch.fnmatch(k, pattern)
            ]
            for key in keys_to_remove:
                del self.cache[key]
```

---

## Advanced Features

### 1. Dynamic Layer Creation

Allow users to create virtual layers on-the-fly:

```bash
# Create a new virtual layer via control socket
$ shadowfs-ctl create-layer by-author \
    --type classifier \
    --classifier git_author \
    --mount /mnt/shadowfs

# Result: new /mnt/shadowfs/by-author/ directory appears
```

### 2. Saved Queries as Directories

Virtual directories that represent complex queries:

```yaml
virtual_layers:
  - name: queries
    type: saved_query
    queries:
      important-and-recent:
        filter: "tags.contains('important') and mtime > now() - 7days"
      
      large-python-files:
        filter: "extension == '.py' and size > 1MB"
      
      untested-code:
        filter: "extension == '.py' and not exists(test_*.py)"
```

### 3. Writable Virtual Layers

Allow writes through virtual layers (with special semantics):

```python
def write_through_virtual_layer(self, virtual_path: str, data: bytes):
    """
    Write through virtual layer.
    
    Semantics:
    - Writing to /by-type/python/newfile.py creates real file
    - Automatically tagged/classified based on virtual location
    """
    # Parse virtual path
    parts = virtual_path.split('/')
    layer_name = parts[0]
    category = parts[1]
    filename = parts[2]
    
    # Determine real path based on layer rules
    if layer_name == "by-type":
        # Create in appropriate source directory
        # Add correct extension if missing
        real_path = self._create_real_path_for_category(category, filename)
    
    # Write file
    with open(real_path, 'wb') as f:
        f.write(data)
    
    # Rebuild indexes
    self.vl_manager.refresh()
```

### 4. Computed Virtual Files

Virtual files that don't exist in source but are computed:

```yaml
virtual_layers:
  - name: reports
    type: computed
    files:
      file-count.txt:
        generator: |
          return f"Total files: {len(all_files)}\n"
      
      summary.json:
        generator: |
          import json
          return json.dumps({
            'total_files': len(all_files),
            'by_type': count_by_type(),
            'total_size': sum(f.size for f in all_files)
          })
```

---

## Complete Working Example

```python
#!/usr/bin/env python3
"""
ShadowFS with Virtual Layers - Complete Example
"""

import os
import sys
from fuse import FUSE, Operations, FuseOSError
import errno

class SimpleShadowFS(Operations):
    """Simplified ShadowFS demonstrating virtual layers"""
    
    def __init__(self, source: str):
        self.source = source
        
        # Build virtual layers
        self.vl_manager = VirtualLayerManager([source])
        
        # Add by-type layer
        type_layer = ClassifierLayer(
            name="by-type",
            classifier=lambda f: f.extension.lstrip('.') or 'no-ext'
        )
        self.vl_manager.add_layer(type_layer)
        
        # Scan and build indexes
        self.vl_manager.scan_sources()
        self.vl_manager.rebuild_indexes()
    
    def getattr(self, path, fh=None):
        # Try virtual resolution
        real_path = self.vl_manager.resolve_path(path)
        
        if real_path:
            st = os.lstat(real_path)
            return dict((key, getattr(st, key)) for key in (
                'st_atime', 'st_ctime', 'st_gid', 'st_mode',
                'st_mtime', 'st_nlink', 'st_size', 'st_uid'))
        
        # Check if virtual directory
        if path == '/' or self._is_virtual_dir(path):
            return {
                'st_mode': 0o40755,
                'st_nlink': 2,
                'st_size': 4096,
            }
        
        raise FuseOSError(errno.ENOENT)
    
    def readdir(self, path, fh):
        if self._is_virtual_path(path):
            return ['.', '..'] + self.vl_manager.list_directory(path)
        
        raise FuseOSError(errno.ENOENT)
    
    def open(self, path, flags):
        real_path = self.vl_manager.resolve_path(path)
        if real_path:
            return os.open(real_path, flags)
        raise FuseOSError(errno.ENOENT)
    
    def read(self, path, size, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, size)
    
    def release(self, path, fh):
        return os.close(fh)
    
    def _is_virtual_path(self, path):
        parts = path.strip('/').split('/', 1)
        if not parts or not parts[0]:
            return True
        return parts[0] in self.vl_manager.list_layers()
    
    def _is_virtual_dir(self, path):
        try:
            self.vl_manager.list_directory(path)
            return True
        except:
            return False


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('usage: %s <source> <mountpoint>' % sys.argv[0])
        sys.exit(1)
    
    source = sys.argv[1]
    mountpoint = sys.argv[2]
    
    # Mount filesystem
    FUSE(SimpleShadowFS(source), mountpoint, foreground=True, allow_other=True)
```

**Usage:**
```bash
# Create test files
mkdir /tmp/source
echo "print('hello')" > /tmp/source/test.py
echo "console.log('hi')" > /tmp/source/app.js
echo "# README" > /tmp/source/README.md

# Mount ShadowFS
python shadowfs_virtual.py /tmp/source /mnt/shadowfs

# Explore virtual layers
$ ls /mnt/shadowfs/
by-type

$ ls /mnt/shadowfs/by-type/
js  md  py

$ ls /mnt/shadowfs/by-type/py/
test.py

$ cat /mnt/shadowfs/by-type/py/test.py
print('hello')
```

---

## Summary

Virtual Layers add a powerful organizational dimension to ShadowFS:

✅ **Multiple Views**: Same files organized different ways
✅ **Zero Duplication**: Files appear in multiple places without copying
✅ **Dynamic Updates**: Virtual structure updates as files change
✅ **Configurable**: Define any classification scheme via YAML
✅ **Extensible**: Custom classifiers and hierarchies
✅ **Performant**: Cached indexes, incremental updates

**Use Cases**:
- Development environments (organize by type, project, status)
- Photo libraries (by date, camera, tags)
- Document management (by author, category, date)
- Media libraries (by genre, artist, year)
- Log analysis (by severity, service, time)

The virtual layer system transforms ShadowFS from a simple filter/transform filesystem into a **dynamic organizational framework** where the directory structure itself becomes programmable!