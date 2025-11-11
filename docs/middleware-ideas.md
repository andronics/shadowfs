# Innovative Filesystem Middleware Patterns for ShadowFS

*Extending ShadowFS with proven middleware patterns from the FUSE ecosystem*

---

## Overview

Based on research into existing FUSE filesystems, here are powerful middleware patterns that could enhance ShadowFS beyond its current filtering, transformation, and virtual layer capabilities.

---

## 1. Deduplication Middleware

### The Pattern

Store only unique blocks of data, with multiple files referencing the same blocks via content hashing.

### How It Works

```
Traditional Storage:
file1.txt: "Hello World" (11 bytes)
file2.txt: "Hello World" (11 bytes)
Total: 22 bytes

With Deduplication:
Block DB: "Hello World" → SHA256 hash (stored once)
file1.txt → points to hash
file2.txt → points to hash
Total: 11 bytes + 2 pointers
```

### Mechanism

1. **Block-Level Chunking**: Files split into fixed-size blocks (4KB, 64KB, 128KB)
2. **Content Hashing**: Each block gets SHA256 hash
3. **Hash Index**: Database maps hash → block content
4. **Metadata Store**: Files store: `[(offset, block_hash), ...]`

### Implementation for ShadowFS

```python
class DeduplicationLayer:
    """
    Middleware that transparently deduplicates file content.
    """
    
    def __init__(self, block_size: int = 4096):
        self.block_size = block_size
        self.block_store = {}  # hash → block content
        self.file_metadata = {}  # path → [(offset, hash), ...]
    
    def write(self, path: str, data: bytes, offset: int):
        """Write with automatic deduplication"""
        blocks = self._split_into_blocks(data)
        block_refs = []
        
        for block in blocks:
            block_hash = hashlib.sha256(block).hexdigest()
            
            # Store block only if not exists
            if block_hash not in self.block_store:
                self.block_store[block_hash] = block
            
            block_refs.append((offset, block_hash))
            offset += len(block)
        
        self.file_metadata[path] = block_refs
    
    def read(self, path: str, size: int, offset: int) -> bytes:
        """Read by reconstructing from deduplicated blocks"""
        block_refs = self.file_metadata[path]
        result = b''
        
        for block_offset, block_hash in block_refs:
            if block_offset >= offset and block_offset < offset + size:
                result += self.block_store[block_hash]
        
        return result[offset:offset+size]
```

### Configuration

```yaml
middleware:
  - name: deduplication
    type: dedup
    block_size: 65536  # 64KB blocks
    hash_algorithm: sha256
    backend_db: ~/.shadowfs/dedup.db
    compression: zlib  # Optional: compress blocks too
```

### Use Cases

- **Backup Storage**: Multiple backups share 90%+ identical blocks
- **VM Images**: Base images deduplicated across VMs
- **Development**: node_modules folders across projects
- **Time-Machine Style Backups**: Incremental backups with minimal storage

### Performance Considerations

Deduplication is CPU-intensive and may be slower for primary storage - best for archival/backup use

**Optimization**:
- Cache hot blocks in memory
- Async deduplication (write-through, dedupe later)
- Tunable block size (larger = faster, less dedup)

---

## 2. Versioning Middleware (Time-Travel Filesystem)

### The Pattern

Automatically create snapshots of every file change, exposing version history as a virtual directory structure.

### How It Works

```
Physical writes:
echo "v1" > file.txt
echo "v2" > file.txt
echo "v3" > file.txt

Virtual structure:
/mnt/shadowfs/
├── file.txt              ← current version (v3)
└── .history/
    └── file.txt/
        ├── 2024-11-11_10:00:00  ← v1
        ├── 2024-11-11_10:05:00  ← v2
        └── 2024-11-11_10:10:00  ← v3 (same as current)
```

### Mechanism

1. **Copy-on-Write**: Before overwriting, save old version
2. **Snapshot Metadata**: Store: `(path, timestamp, version_id)`
3. **Virtual History Directory**: Expose snapshots as read-only files

### Implementation for ShadowFS

```python
class VersioningLayer:
    """
    Middleware that maintains complete file history.
    
    Similar to Time Machine or Git for every file.
    """
    
    def __init__(self, history_dir: str = ".history"):
        self.history_dir = history_dir
        self.versions = {}  # path → [(timestamp, version_id), ...]
        self.version_store = {}  # version_id → content
    
    def write(self, path: str, data: bytes):
        """Write with automatic versioning"""
        # Generate version ID
        version_id = f"{path}_{time.time()}"
        timestamp = datetime.now()
        
        # Save version
        self.version_store[version_id] = data
        
        # Update metadata
        if path not in self.versions:
            self.versions[path] = []
        self.versions[path].append((timestamp, version_id))
    
    def list_versions(self, path: str) -> List[Tuple[datetime, str]]:
        """List all versions of a file"""
        return self.versions.get(path, [])
    
    def read_version(self, path: str, timestamp: datetime) -> bytes:
        """Read specific version by timestamp"""
        versions = self.versions[path]
        
        # Find version at or before timestamp
        for ts, version_id in reversed(versions):
            if ts <= timestamp:
                return self.version_store[version_id]
        
        raise FileNotFoundError("No version at that timestamp")
```

### Virtual Directory Integration

```python
def readdir(self, path: str) -> List[str]:
    """Expose history as virtual directories"""
    if path.endswith(".history"):
        # List all files with history
        return [f for f in self.versions.keys()]
    
    elif path.startswith(".history/"):
        # List versions of specific file
        file_path = path.replace(".history/", "")
        versions = self.list_versions(file_path)
        return [ts.isoformat() for ts, _ in versions]
    
    # Normal directory listing
    return self._list_normal_dir(path)
```

### Configuration

```yaml
middleware:
  - name: versioning
    type: time_machine
    history_location: .history  # Virtual directory name
    max_versions: 100  # Keep last N versions
    retention_days: 30  # Keep versions for N days
    auto_snapshot: true
    snapshot_interval: 300  # Snapshot every 5 minutes
```

### Use Cases

- **Document Editing**: Never lose a version
- **Configuration Files**: Rollback bad changes
- **Code Development**: Complement Git with filesystem-level history
- **Accidental Deletes**: Recover from `.history/deleted/`

---

## 3. Compression Middleware

### The Pattern

Transparently compress blocks before storage, decompress on read.

### How It Works

```
Application writes: "Hello World" * 1000 (11KB)
↓
Compression layer: compress with zlib
↓
Storage: compressed block (maybe 500 bytes)
↓
Application reads: "Hello World" * 1000 (11KB decompressed)
```

### Implementation for ShadowFS

```python
class CompressionLayer:
    """
    Middleware for transparent compression.
    
    Can be combined with deduplication for maximum space savings.
    """
    
    def __init__(self, algorithm: str = "zlib", level: int = 6):
        self.algorithm = algorithm
        self.level = level
        self.compressed_blocks = {}  # path → compressed_data
        self.original_sizes = {}  # path → original_size
    
    def write(self, path: str, data: bytes):
        """Compress on write"""
        if self.algorithm == "zlib":
            compressed = zlib.compress(data, self.level)
        elif self.algorithm == "lzma":
            compressed = lzma.compress(data)
        elif self.algorithm == "bz2":
            compressed = bz2.compress(data)
        
        self.compressed_blocks[path] = compressed
        self.original_sizes[path] = len(data)
    
    def read(self, path: str) -> bytes:
        """Decompress on read"""
        compressed = self.compressed_blocks[path]
        
        if self.algorithm == "zlib":
            return zlib.decompress(compressed)
        elif self.algorithm == "lzma":
            return lzma.decompress(compressed)
        elif self.algorithm == "bz2":
            return bz2.decompress(compressed)
    
    def getattr(self, path: str) -> Dict:
        """Report original size, not compressed size"""
        attrs = self._get_real_attrs(path)
        # Override size to show uncompressed size
        attrs['st_size'] = self.original_sizes[path]
        return attrs
```

### Configuration

```yaml
middleware:
  - name: compression
    type: compress
    algorithm: zlib  # zlib, lzma, bz2, zstd
    level: 6  # Compression level (1-9)
    min_file_size: 4096  # Only compress files > 4KB
    blacklist_extensions:  # Don't compress already compressed
      - .jpg
      - .png
      - .zip
      - .gz
```

### Use Cases

- **Log Files**: Compress old logs automatically
- **Text Documents**: High compression ratios
- **Source Code**: Save space on large codebases
- **Archival Storage**: Maximize storage efficiency

---

## 4. Encryption Middleware

### The Pattern

Transparently encrypt data before storage using AES or ChaCha20, decrypt on read.

### How It Works

```
Application writes: sensitive data
↓
Encryption layer: AES-256-GCM encrypt
↓
Storage: ciphertext + IV + auth tag
↓
Application reads: decrypted sensitive data
```

### Implementation for ShadowFS

```python
class EncryptionLayer:
    """
    Middleware for transparent encryption.
    
    Files stored encrypted, appear decrypted to applications.
    """
    
    def __init__(self, key: bytes, algorithm: str = "AES-256-GCM"):
        self.key = key
        self.algorithm = algorithm
        self.encrypted_blocks = {}  # path → (ciphertext, iv, tag)
    
    def write(self, path: str, data: bytes):
        """Encrypt on write"""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        
        aesgcm = AESGCM(self.key)
        iv = os.urandom(12)  # 96-bit nonce for GCM
        
        # Encrypt with associated data (path as AAD)
        ciphertext = aesgcm.encrypt(iv, data, path.encode())
        
        self.encrypted_blocks[path] = (ciphertext, iv)
    
    def read(self, path: str) -> bytes:
        """Decrypt on read"""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        
        ciphertext, iv = self.encrypted_blocks[path]
        aesgcm = AESGCM(self.key)
        
        # Decrypt and verify
        plaintext = aesgcm.decrypt(iv, ciphertext, path.encode())
        return plaintext
```

### Configuration

```yaml
middleware:
  - name: encryption
    type: encrypt
    algorithm: AES-256-GCM
    key_source: env:SHADOWFS_ENCRYPTION_KEY  # or file:/path/to/key
    encrypted_paths:
      - /secrets/**
      - /private/**
    metadata_encryption: true  # Encrypt filenames too
```

### Use Cases

- **Sensitive Documents**: Encrypt financial records, medical data
- **Cloud Backup**: Encrypt before uploading to cloud
- **Compliance**: HIPAA, GDPR requirements
- **Portable Storage**: Encrypted USB drives

### Advanced: Per-File Keys

```python
class PerFileEncryptionLayer(EncryptionLayer):
    """Use different key per file for enhanced security"""
    
    def __init__(self, master_key: bytes):
        self.master_key = master_key
        self.file_keys = {}  # path → encrypted_file_key
    
    def _derive_file_key(self, path: str) -> bytes:
        """Derive unique key per file"""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=path.encode(),
            iterations=100000,
        )
        return kdf.derive(self.master_key)
```

---

## 5. Full-Text Search Index Middleware

### The Pattern

Automatically index file content for fast full-text search, using filesystem monitoring with inotify to trigger indexing of new/changed files immediately.

### How It Works

```
File written → inotify event → Extract text → Index
                                                ↓
User searches: "project deadline" → Query index → Return matching files
```

### Implementation for ShadowFS

```python
class SearchIndexLayer:
    """
    Middleware that maintains full-text search index.
    
    Exposes virtual files like .search/query/results
    """
    
    def __init__(self, index_dir: str):
        from whoosh.index import create_in
        from whoosh.fields import Schema, TEXT, ID
        
        schema = Schema(
            path=ID(stored=True, unique=True),
            content=TEXT(stored=True),
            mtime=ID(stored=True)
        )
        
        self.index = create_in(index_dir, schema)
        self.writer = self.index.writer()
    
    def on_file_written(self, path: str, content: bytes):
        """Index file content automatically"""
        try:
            # Extract text (handle different formats)
            text = self._extract_text(path, content)
            
            # Update index
            self.writer.update_document(
                path=path,
                content=text,
                mtime=str(time.time())
            )
            self.writer.commit()
            
        except Exception as e:
            logger.error(f"Failed to index {path}: {e}")
    
    def search(self, query: str) -> List[str]:
        """Full-text search across all files"""
        from whoosh.qparser import QueryParser
        
        with self.index.searcher() as searcher:
            query_obj = QueryParser("content", self.index.schema).parse(query)
            results = searcher.search(query_obj)
            return [r['path'] for r in results]
    
    def _extract_text(self, path: str, content: bytes) -> str:
        """Extract searchable text from various formats"""
        ext = os.path.splitext(path)[1]
        
        if ext in ['.txt', '.md', '.py', '.js']:
            return content.decode('utf-8', errors='ignore')
        
        elif ext == '.pdf':
            import PyPDF2
            # Extract text from PDF
            pass
        
        elif ext in ['.docx', '.odt']:
            # Extract from document
            pass
        
        return ""
```

### Virtual Search Interface

```python
def readdir(self, path: str) -> List[str]:
    """Expose search via virtual directories"""
    if path == "/.search":
        return ["query"]
    
    elif path.startswith("/.search/query/"):
        # Path like: /.search/query/project deadline
        query = path.replace("/.search/query/", "")
        results = self.search_index.search(query)
        
        # Return matching file names as symlinks
        return [os.path.basename(r) for r in results]
```

### Configuration

```yaml
middleware:
  - name: search_index
    type: fulltext_search
    index_dir: ~/.shadowfs/search_index
    index_formats:
      - .txt
      - .md
      - .py
      - .pdf
      - .docx
    virtual_search_dir: .search
    realtime_indexing: true  # Use inotify for instant indexing
```

### Use Cases

- **Document Libraries**: Find documents by content
- **Code Search**: Search across all codebases
- **Email Archives**: Full-text email search
- **Research**: Search PDFs and papers

---

## 6. Git-Aware Middleware

### The Pattern

Integrate Git directly into filesystem - writes automatically become commits, history exposed as directories.

### How It Works

```
User writes file → Automatic git commit
User reads /.git/history/2024-11-10/ → See files as they were on that date
```

### Implementation for ShadowFS

```python
class GitAwareLayer:
    """
    Middleware that automatically commits changes to Git.
    
    Every write becomes a commit, history browseable as filesystem.
    """
    
    def __init__(self, repo_path: str):
        import git
        self.repo = git.Repo(repo_path)
    
    def write(self, path: str, data: bytes):
        """Write file and auto-commit"""
        # Write to actual file
        real_path = self._get_real_path(path)
        with open(real_path, 'wb') as f:
            f.write(data)
        
        # Stage and commit
        self.repo.index.add([real_path])
        self.repo.index.commit(
            f"Auto-commit: {path}",
            author=git.Actor("ShadowFS", "shadowfs@local")
        )
    
    def list_history(self, path: str) -> List[Tuple[datetime, str]]:
        """List all commits that modified this file"""
        commits = list(self.repo.iter_commits(paths=path))
        return [(c.committed_datetime, c.hexsha) for c in commits]
    
    def read_at_commit(self, path: str, commit_sha: str) -> bytes:
        """Read file as it was at a specific commit"""
        commit = self.repo.commit(commit_sha)
        blob = commit.tree / path
        return blob.data_stream.read()
```

### Virtual Git Interface

```python
def readdir(self, path: str) -> List[str]:
    """Expose Git history as directories"""
    if path == "/.git/history":
        # List dates with commits
        commits = self.repo.iter_commits()
        dates = set(c.committed_datetime.date() for c in commits)
        return [str(d) for d in sorted(dates)]
    
    elif path.startswith("/.git/history/"):
        # Show files as of that date
        date_str = path.split("/")[-1]
        date = datetime.strptime(date_str, "%Y-%m-%d")
        
        # Find commit closest to that date
        commit = self._find_commit_by_date(date)
        
        # List files in that commit
        return [item.path for item in commit.tree.traverse()]
```

### Configuration

```yaml
middleware:
  - name: git_integration
    type: git_aware
    repo_path: .
    auto_commit: true
    commit_message_template: "Auto: {file} changed by {user}"
    branch: auto-commits
    
    # Virtual directories
    history_dir: .git/history  # Browse by date
    commits_dir: .git/commits  # Browse by commit
    branches_dir: .git/branches  # Switch branches
```

### Use Cases

- **Automatic Versioning**: Every save is a commit
- **Non-Git Users**: Git benefits without knowing Git
- **Collaborative Editing**: Track who changed what
- **Time-Travel**: Browse filesystem at any point in history

---

## 7. Cloud Sync Middleware

### The Pattern

Transparently sync files to cloud storage (S3, Google Drive, Dropbox), with local cache for performance.

### How It Works

```
Application writes → Local cache + async upload to cloud
Application reads → Serve from local cache (or fetch if not cached)
```

### Implementation for ShadowFS

```python
class CloudSyncLayer:
    """
    Middleware for transparent cloud synchronization.
    
    Files cached locally, synced to cloud in background.
    """
    
    def __init__(self, cloud_backend: str, cache_dir: str):
        self.backend = self._init_backend(cloud_backend)
        self.cache = CacheManager(cache_dir)
        self.sync_queue = queue.Queue()
        
        # Background sync thread
        self.sync_thread = threading.Thread(target=self._sync_worker)
        self.sync_thread.daemon = True
        self.sync_thread.start()
    
    def write(self, path: str, data: bytes):
        """Write to cache and queue for cloud sync"""
        # Write to local cache immediately
        self.cache.write(path, data)
        
        # Queue for cloud upload
        self.sync_queue.put(('upload', path, data))
    
    def read(self, path: str) -> bytes:
        """Read from cache, or fetch from cloud"""
        # Try cache first
        if self.cache.has(path):
            return self.cache.read(path)
        
        # Fetch from cloud
        data = self.backend.download(path)
        
        # Cache for future reads
        self.cache.write(path, data)
        
        return data
    
    def _sync_worker(self):
        """Background thread that syncs to cloud"""
        while True:
            operation, path, data = self.sync_queue.get()
            
            if operation == 'upload':
                try:
                    self.backend.upload(path, data)
                except Exception as e:
                    logger.error(f"Cloud sync failed for {path}: {e}")
                    # Re-queue for retry
                    self.sync_queue.put((operation, path, data))
```

### Configuration

```yaml
middleware:
  - name: cloud_sync
    type: cloud
    backend: s3  # s3, gdrive, dropbox, azure
    
    # S3 configuration
    s3:
      bucket: my-shadowfs-bucket
      region: us-east-1
      access_key_id: env:AWS_ACCESS_KEY_ID
      secret_access_key: env:AWS_SECRET_ACCESS_KEY
    
    # Cache configuration
    cache_dir: ~/.shadowfs/cache
    cache_size_gb: 10
    cache_policy: lru  # lru, lfu, or keep_recent
    
    # Sync behavior
    sync_mode: async  # async or sync
    retry_attempts: 3
    offline_mode: true  # Work offline, sync when online
```

### Use Cases

- **Distributed Teams**: Sync files across team members
- **Backup**: Automatic cloud backup
- **Mobile Access**: Access files from anywhere
- **Disaster Recovery**: Cloud copy for resilience

---

## 8. Content-Addressed Storage (CAS) Middleware

### The Pattern

Store files by content hash, automatically deduplicate at the object level.

### How It Works

```
Store file → Hash content → Store as hash-named object
Multiple files with same content → Same hash → Single storage
```

### Implementation for ShadowFS

```python
class ContentAddressedLayer:
    """
    Middleware using content-addressed storage.
    
    Files stored by content hash, enabling natural deduplication.
    """
    
    def __init__(self, object_store: str):
        self.object_store = object_store
        self.metadata = {}  # path → hash
        self.objects = {}  # hash → content
    
    def write(self, path: str, data: bytes):
        """Store by content hash"""
        content_hash = hashlib.sha256(data).hexdigest()
        
        # Store object if doesn't exist
        if content_hash not in self.objects:
            self.objects[content_hash] = data
        
        # Update path → hash mapping
        self.metadata[path] = content_hash
    
    def read(self, path: str) -> bytes:
        """Read via content hash"""
        content_hash = self.metadata[path]
        return self.objects[content_hash]
    
    def copy(self, src: str, dst: str):
        """Copy is just metadata operation - no data copy!"""
        self.metadata[dst] = self.metadata[src]
        # Object already exists, just reference it
    
    def get_storage_efficiency(self) -> float:
        """Calculate deduplication ratio"""
        logical_size = sum(len(self.objects[h]) 
                          for h in self.metadata.values())
        physical_size = sum(len(c) for c in self.objects.values())
        return logical_size / physical_size
```

### Configuration

```yaml
middleware:
  - name: content_addressed
    type: cas
    object_store: ~/.shadowfs/objects
    hash_algorithm: sha256
    gc_enabled: true  # Garbage collect unreferenced objects
    gc_interval: 86400  # Daily
```

### Use Cases

- **VM Images**: Share base image blocks
- **Container Layers**: Docker-style layer sharing
- **Snapshots**: Fast snapshots via copy-on-write
- **Backups**: Incremental backups naturally deduplicated

---

## 9. Quota & Rate Limiting Middleware

### The Pattern

Enforce per-user storage quotas and I/O rate limits.

### Implementation for ShadowFS

```python
class QuotaLayer:
    """
    Middleware for enforcing storage quotas and rate limits.
    """
    
    def __init__(self):
        self.user_quotas = {}  # user → (used_bytes, max_bytes)
        self.rate_limits = {}  # user → (ops_count, window_start)
    
    def check_quota(self, user: str, additional_bytes: int) -> bool:
        """Check if user has space available"""
        used, max_quota = self.user_quotas.get(user, (0, float('inf')))
        return (used + additional_bytes) <= max_quota
    
    def check_rate_limit(self, user: str) -> bool:
        """Check if user exceeded rate limit"""
        ops, window_start = self.rate_limits.get(user, (0, time.time()))
        
        # Reset window if expired
        if time.time() - window_start > 60:  # 1 minute window
            self.rate_limits[user] = (1, time.time())
            return True
        
        # Check limit
        max_ops_per_minute = 1000
        if ops < max_ops_per_minute:
            self.rate_limits[user] = (ops + 1, window_start)
            return True
        
        return False
    
    def write(self, user: str, path: str, data: bytes):
        """Write with quota checking"""
        if not self.check_quota(user, len(data)):
            raise FuseOSError(errno.EDQUOT)  # Disk quota exceeded
        
        if not self.check_rate_limit(user):
            raise FuseOSError(errno.EBUSY)  # Rate limited
        
        # Proceed with write
        self._do_write(path, data)
        
        # Update quota
        used, max_quota = self.user_quotas[user]
        self.user_quotas[user] = (used + len(data), max_quota)
```

### Configuration

```yaml
middleware:
  - name: quotas
    type: quota
    per_user:
      alice: 10GB
      bob: 5GB
      default: 1GB
    
    rate_limits:
      max_ops_per_minute: 1000
      max_bandwidth_mbps: 100
```

---

## 10. Audit & Compliance Middleware

### The Pattern

Log all filesystem operations for security auditing and compliance.

### Implementation for ShadowFS

```python
class AuditLayer:
    """
    Middleware that logs all filesystem operations.
    
    Critical for security, compliance, forensics.
    """
    
    def __init__(self, audit_log: str):
        self.audit_log = audit_log
        self.logger = self._setup_logger()
    
    def audit(self, operation: str, user: str, path: str, 
              result: str, metadata: Dict = None):
        """Log audit event"""
        event = {
            'timestamp': time.time(),
            'operation': operation,
            'user': user,
            'path': path,
            'result': result,
            'metadata': metadata or {},
            'source_ip': self._get_source_ip()
        }
        
        self.logger.info(json.dumps(event))
    
    def read(self, user: str, path: str) -> bytes:
        """Read with audit logging"""
        try:
            data = self._do_read(path)
            self.audit('read', user, path, 'success', 
                      {'size': len(data)})
            return data
        except Exception as e:
            self.audit('read', user, path, 'failure', 
                      {'error': str(e)})
            raise
    
    def write(self, user: str, path: str, data: bytes):
        """Write with audit logging"""
        try:
            self._do_write(path, data)
            self.audit('write', user, path, 'success',
                      {'size': len(data)})
        except Exception as e:
            self.audit('write', user, path, 'failure',
                      {'error': str(e)})
            raise
```

### Configuration

```yaml
middleware:
  - name: audit
    type: audit_log
    log_file: /var/log/shadowfs/audit.log
    log_operations:
      - read
      - write
      - delete
      - chmod
      - chown
    
    retention_days: 365
    syslog_enabled: true
    siem_integration: splunk  # or elastic, datadog
```

---

## Middleware Stacking

### The Power of Composition

Middleware layers can be stacked for powerful combinations:

```yaml
middleware_stack:
  # Layer 1: Quota enforcement (first check)
  - name: quotas
    type: quota
    per_user_limit: 10GB
  
  # Layer 2: Audit logging (log everything)
  - name: audit
    type: audit_log
  
  # Layer 3: Encryption (secure at rest)
  - name: encryption
    type: encrypt
    algorithm: AES-256-GCM
  
  # Layer 4: Compression (save space)
  - name: compression
    type: compress
    algorithm: zlib
  
  # Layer 5: Deduplication (maximize efficiency)
  - name: dedup
    type: deduplication
    block_size: 64KB
  
  # Layer 6: Cloud sync (backup)
  - name: cloud
    type: cloud_sync
    backend: s3
  
  # Layer 7: Versioning (time travel)
  - name: versions
    type: time_machine
    retention_days: 30
```

**Data Flow**:
```
Application Write
  ↓
Quota Check → Audit Log → Encrypt → Compress → Dedupe → Cloud Sync → Version
  ↓
Storage
```

---

## Integration with Existing ShadowFS Components

### How Middleware Integrates

```python
class ShadowFS(Operations):
    """Enhanced ShadowFS with middleware support"""
    
    def __init__(self, config: Config):
        # Existing components
        self.rule_engine = RuleEngine(config.rules)
        self.transform_pipeline = TransformPipeline(config.transforms)
        self.virtual_layers = VirtualLayerManager(config.virtual_layers)
        
        # NEW: Middleware stack
        self.middleware_stack = MiddlewareStack()
        self._load_middleware(config.middleware)
    
    def _load_middleware(self, middleware_config: List[Dict]):
        """Load middleware in order"""
        for mw_config in middleware_config:
            middleware = create_middleware(mw_config)
            self.middleware_stack.add(middleware)
    
    def write(self, path: str, data: bytes, offset: int, fh: int):
        """Write with middleware processing"""
        # Resolve virtual path
        real_path = self.virtual_layers.resolve_path(path)
        
        # Apply middleware stack (in order)
        processed_data = self.middleware_stack.process_write(
            path=real_path,
            data=data,
            user=self._get_current_user()
        )
        
        # Write to storage
        return self._write_to_storage(real_path, processed_data, offset)
    
    def read(self, path: str, size: int, offset: int, fh: int):
        """Read with middleware processing"""
        # Resolve virtual path
        real_path = self.virtual_layers.resolve_path(path)
        
        # Read from storage
        data = self._read_from_storage(real_path, size, offset)
        
        # Apply middleware stack (in reverse order for read)
        processed_data = self.middleware_stack.process_read(
            path=real_path,
            data=data,
            user=self._get_current_user()
        )
        
        return processed_data
```

---

## Recommended Middleware Combinations

### Combination 1: Backup & Archival
```yaml
middleware:
  - deduplication
  - compression
  - encryption
  - cloud_sync
```

**Use Case**: Efficient, secure backups with cloud storage

---

### Combination 2: Development Environment
```yaml
middleware:
  - versioning
  - git_integration
  - search_index
```

**Use Case**: Track all changes, search across codebases

---

### Combination 3: Compliance & Security
```yaml
middleware:
  - quota
  - audit_log
  - encryption
  - rate_limiting
```

**Use Case**: Meet regulatory requirements (HIPAA, SOX, GDPR)

---

### Combination 4: Collaborative Workspace
```yaml
middleware:
  - versioning
  - cloud_sync
  - search_index
  - audit_log
```

**Use Case**: Team collaboration with history and search

---

## Implementation Priority

### Phase 1: Foundation (Weeks 1-2)
- Middleware abstraction layer
- Basic middleware interface

### Phase 2: Storage Optimization (Weeks 3-5)
- Deduplication middleware
- Compression middleware
- Content-addressed storage

### Phase 3: Security & Compliance (Weeks 6-8)
- Encryption middleware
- Audit logging middleware
- Quota management

### Phase 4: Advanced Features (Weeks 9-12)
- Versioning middleware
- Git integration
- Search indexing
- Cloud sync

---

## Summary

These middleware patterns, proven in production FUSE filesystems, can dramatically extend ShadowFS capabilities:

✅ **Storage Efficiency**: Deduplication, compression, CAS
✅ **Security**: Encryption, audit logging, quotas
✅ **Versioning**: Time-travel, Git integration
✅ **Search**: Full-text indexing with inotify
✅ **Cloud Integration**: Transparent sync to S3/Drive
✅ **Composability**: Stack multiple middleware layers

Each middleware is **orthogonal** - they can be enabled/disabled independently and combined in any order for maximum flexibility.

---

**References**:
- [architecture.md](architecture.md) - Core architecture
- [virtual-layers.md](virtual-layers.md) - Virtual directory organization
- [CLAUDE.md](../CLAUDE.md) - Project overview