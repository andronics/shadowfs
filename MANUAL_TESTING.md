# ShadowFS CLI Manual Testing Guide

Quick reference for manually testing the ShadowFS command-line interface.

## Quick Start (30 seconds)

```bash
# 1. Install in development mode
pip install -e .

# 2. Check it worked
shadowfs --version
shadowfs --help

# 3. Run the automated test script
./test_cli_manual.sh
```

## Method 1: Simple Test (Recommended for First Test)

```bash
# Install
pip install -e .

# Create test directories
mkdir -p /tmp/shadowfs-demo/{source,mount}
echo "Hello World" > /tmp/shadowfs-demo/source/test.txt

# Mount (foreground mode for easy testing)
shadowfs --sources /tmp/shadowfs-demo/source --mount /tmp/shadowfs-demo/mount --foreground --debug

# In another terminal:
ls -la /tmp/shadowfs-demo/mount
cat /tmp/shadowfs-demo/mount/test.txt

# Unmount (Ctrl+C in the first terminal, or):
fusermount -u /tmp/shadowfs-demo/mount  # Linux
umount /tmp/shadowfs-demo/mount         # macOS

# Cleanup
rm -rf /tmp/shadowfs-demo
```

## Method 2: Test Without Installing

```bash
# Run directly with Python
python -m shadowfs.main --help
python -m shadowfs.main --version

# Or run the module
PYTHONPATH=. python shadowfs/main.py --help
```

## Method 3: Test with Configuration File

```bash
# Create a test config
cat > /tmp/shadowfs-test.yaml << 'EOF'
shadowfs:
  version: "1.0"

  sources:
    - path: /tmp/test-source
      priority: 1

  rules:
    - name: "Show all files"
      type: include
      pattern: "**/*"

  cache:
    enabled: true
    max_size_mb: 100

  logging:
    level: DEBUG
EOF

# Create test source
mkdir -p /tmp/test-source /tmp/test-mount
echo "Config test" > /tmp/test-source/config-test.txt

# Mount with config
shadowfs --config /tmp/shadowfs-test.yaml --mount /tmp/test-mount --foreground

# Test in another terminal
ls /tmp/test-mount
cat /tmp/test-mount/config-test.txt
```

## Method 4: Interactive Testing

```bash
# Start Python REPL with CLI imported
python3 << 'EOF'
from shadowfs.cli import parse_arguments, validate_runtime_environment

# Test argument parsing
args = parse_arguments(['--sources', '/tmp', '--mount', '/tmp/mnt'])
print(f"Parsed args: {args}")

# Test validation (will check for FUSE availability)
try:
    validate_runtime_environment()
    print("Runtime environment OK")
except Exception as e:
    print(f"Environment issue: {e}")
EOF
```

## Command Reference

### Main Mount Command

```bash
# Basic mount
shadowfs --sources /data --mount /mnt/shadowfs

# Multiple sources
shadowfs --sources /data /backup /archive --mount /mnt/shadowfs

# With config file
shadowfs --config /etc/shadowfs/config.yaml --mount /mnt/shadowfs

# Foreground mode (for debugging)
shadowfs --sources /data --mount /mnt/shadowfs --foreground

# Debug logging
shadowfs --sources /data --mount /mnt/shadowfs --debug

# Read-write mode
shadowfs --sources /data --mount /mnt/shadowfs --read-write

# Allow other users
shadowfs --sources /data --mount /mnt/shadowfs --allow-other

# Custom cache size
shadowfs --sources /data --mount /mnt/shadowfs --cache-size 1024

# Disable cache
shadowfs --sources /data --mount /mnt/shadowfs --no-cache
```

### Control Commands (shadowfs-ctl)

```bash
# Get status (when mounted)
shadowfs-ctl status

# Get statistics
shadowfs-ctl stats

# Reload configuration
shadowfs-ctl reload

# List virtual layers
shadowfs-ctl list-layers

# Clear cache
shadowfs-ctl clear-cache
```

## Testing Checklist

### Basic Functionality
- [ ] `shadowfs --version` shows version
- [ ] `shadowfs --help` shows help
- [ ] Can mount with `--sources`
- [ ] Can read files through mount point
- [ ] Can unmount cleanly

### Configuration
- [ ] Can load YAML config with `--config`
- [ ] Invalid config path shows error
- [ ] Config validation catches errors

### Logging
- [ ] `--debug` enables debug logging
- [ ] Log file created at specified path
- [ ] Errors logged correctly

### Edge Cases
- [ ] Mounting non-existent directory fails
- [ ] Invalid source directory shows error
- [ ] Missing mount point shows error
- [ ] Duplicate mount attempt handled

### Performance
- [ ] Cache improves read performance
- [ ] `--no-cache` disables caching
- [ ] Multiple simultaneous reads work

## Troubleshooting

### Command not found

```bash
# Make sure you installed it
pip install -e .

# Check if it's in PATH
which shadowfs

# If not, try:
python -m shadowfs.main --help
```

### FUSE not available

```bash
# Linux
sudo apt-get install fuse libfuse-dev  # Debian/Ubuntu
sudo yum install fuse fuse-devel       # RedHat/CentOS

# macOS
brew install macfuse
```

### Permission denied

```bash
# Add your user to fuse group (Linux)
sudo usermod -a -G fuse $USER

# Or mount with sudo
sudo shadowfs --sources /data --mount /mnt/shadowfs --allow-other
```

### Mount point busy

```bash
# Check what's using it
lsof /mnt/shadowfs

# Force unmount (Linux)
sudo fusermount -u /mnt/shadowfs

# Force unmount (macOS)
sudo umount -f /mnt/shadowfs
```

### Debug mode

```bash
# Run with maximum verbosity
shadowfs --sources /data --mount /mnt/shadowfs --foreground --debug

# Watch logs in real-time
tail -f /var/log/shadowfs/shadowfs.log
```

## Example Test Session

```bash
# 1. Install
pip install -e .

# 2. Create test environment
mkdir -p ~/shadowfs-test/{source,mount}
cd ~/shadowfs-test/source
echo "Test file 1" > file1.txt
echo "Test file 2" > file2.txt
mkdir subdir
echo "Nested" > subdir/nested.txt

# 3. Mount in foreground
shadowfs --sources ~/shadowfs-test/source \
         --mount ~/shadowfs-test/mount \
         --foreground \
         --debug

# 4. In another terminal
cd ~/shadowfs-test/mount
ls -la
cat file1.txt
ls subdir/
cat subdir/nested.txt

# 5. Test writes (if --read-write was used)
echo "New content" > file3.txt
cat file3.txt

# 6. Unmount (Ctrl+C in first terminal or)
fusermount -u ~/shadowfs-test/mount

# 7. Cleanup
rm -rf ~/shadowfs-test
```

## Performance Testing

```bash
# Create large test dataset
mkdir -p /tmp/perf-test/{source,mount}
for i in {1..1000}; do
    echo "File $i content" > /tmp/perf-test/source/file$i.txt
done

# Mount with cache
shadowfs --sources /tmp/perf-test/source \
         --mount /tmp/perf-test/mount \
         --cache-size 512 \
         --foreground

# Benchmark (in another terminal)
time find /tmp/perf-test/mount -type f | wc -l
time cat /tmp/perf-test/mount/file500.txt
```

## Next Steps

After manual testing:
1. Run the full test suite: `pytest tests/`
2. Check coverage: `pytest --cov=shadowfs tests/`
3. Try with real data directories
4. Test virtual layers and transforms
5. Test the control server API
