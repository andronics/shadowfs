# ShadowFS fstab Integration

This guide explains how to mount ShadowFS filesystems automatically at boot using `/etc/fstab`.

## Installation

### 1. Install ShadowFS Package

```bash
pip install shadowfs
# or
python setup.py install
```

### 2. Install Mount Helper

The mount helper needs to be accessible to the `mount` command. Create a symlink to `/sbin/` or `/usr/sbin/`:

**For traditional systems:**
```bash
sudo ln -s $(which mount.shadowfs) /sbin/mount.shadowfs
```

**For systemd-based systems (most modern distributions):**
```bash
sudo ln -s $(which mount.shadowfs) /usr/sbin/mount.shadowfs
```

**Verify installation:**
```bash
ls -l /sbin/mount.shadowfs /usr/sbin/mount.shadowfs
which mount.shadowfs
```

## fstab Configuration

### Basic Syntax

```
source  mountpoint  shadowfs  options  dump  pass
```

### Examples

#### 1. Basic Read-Only Mount

```
/data/source  /mnt/shadowfs  shadowfs  ro,allow_other  0  0
```

#### 2. Read-Write with Custom Config

```
/data/source  /mnt/shadowfs  shadowfs  rw,allow_other,config=/etc/shadowfs/config.yaml  0  0
```

#### 3. With Additional FUSE Options

```
/data/source  /mnt/shadowfs  shadowfs  ro,allow_other,uid=1000,gid=1000,umask=022  0  0
```

#### 4. Debug Mode (for troubleshooting)

```
/data/source  /mnt/shadowfs  shadowfs  ro,allow_other,debug  0  0
```

### Common Options

#### ShadowFS-Specific Options:

- `config=/path/to/config.yaml` - Specify configuration file
- `debug` - Enable debug logging
- `foreground` - Run in foreground (NOT recommended for fstab)

#### Standard FUSE Options:

- `ro` - Mount read-only (default)
- `rw` - Mount read-write
- `allow_other` - Allow all users to access the filesystem
- `allow_root` - Allow only root to access the filesystem
- `uid=N` - Set file owner to UID N
- `gid=N` - Set file group to GID N
- `umask=MASK` - Set permission mask
- `default_permissions` - Enable permission checking by kernel
- `nonempty` - Allow mounting over non-empty directory (use with caution)

#### Dump and Pass Fields:

- `dump` (5th field): Set to `0` (ShadowFS doesn't need backups via dump)
- `pass` (6th field): Set to `0` (no fsck needed for FUSE filesystems)

## Configuration File

When using the `config=` option, create your configuration file at the specified path:

**Example `/etc/shadowfs/config.yaml`:**
```yaml
shadowfs:
  version: "1.0"

  sources:
    - path: /data/documents
      priority: 1

  rules:
    - name: "Hide hidden files"
      type: exclude
      pattern: "**/.*"

  virtual_layers:
    - name: by-type
      type: classifier
      classifier: extension

  cache:
    enabled: true
    max_size_mb: 512
    ttl_seconds: 300

  logging:
    level: INFO
    file: /var/log/shadowfs/shadowfs.log
```

## Mounting and Unmounting

### Manual Operations

**Mount:**
```bash
sudo mount /mnt/shadowfs
```

**Unmount:**
```bash
sudo umount /mnt/shadowfs
```

**Mount all fstab entries:**
```bash
sudo mount -a
```

### Automatic at Boot

Once added to `/etc/fstab`, ShadowFS will mount automatically at boot.

## Troubleshooting

### Check Mount Helper

```bash
# Verify mount helper is found
which mount.shadowfs

# Verify it's executable
ls -l $(which mount.shadowfs)

# Test mount helper directly
/sbin/mount.shadowfs /source /mount -o ro,allow_other -v
```

### Check Logs

```bash
# System logs
sudo journalctl -xe | grep shadowfs
sudo dmesg | grep fuse

# ShadowFS logs (if configured)
sudo tail -f /var/log/shadowfs/shadowfs.log
```

### Common Issues

#### 1. Mount Helper Not Found

**Error**: `mount: unknown filesystem type 'shadowfs'`

**Solution**: Ensure mount helper is installed:
```bash
sudo ln -s $(which mount.shadowfs) /sbin/mount.shadowfs
```

#### 2. Permission Denied

**Error**: `fusermount: option allow_other only allowed if 'user_allow_other' is set in /etc/fuse.conf`

**Solution**: Edit `/etc/fuse.conf` and uncomment:
```bash
sudo nano /etc/fuse.conf
# Uncomment this line:
user_allow_other
```

#### 3. Mount Point Not Empty

**Error**: `Mount point is not empty: /mnt/shadowfs`

**Solution**: Either:
- Empty the mount point
- Add `nonempty` option (not recommended)
- Use a different mount point

#### 4. Source Directory Not Found

**Error**: `Source directory does not exist: /data/source`

**Solution**: Ensure source directory exists and is accessible:
```bash
ls -ld /data/source
```

## Security Considerations

### 1. Permissions

When using `allow_other`, any user can access the mounted filesystem. Consider:

- Using `allow_root` instead for sensitive data
- Setting appropriate `uid`, `gid`, and `umask` options
- Using `default_permissions` for kernel-level permission checks

### 2. Configuration Files

Protect configuration files containing sensitive settings:

```bash
sudo chown root:root /etc/shadowfs/config.yaml
sudo chmod 600 /etc/shadowfs/config.yaml
```

### 3. Auto-Mount Security

For production systems:
- Always mount read-only unless write access is required
- Use configuration files instead of inline options for complex setups
- Regularly review mounted filesystems: `mount | grep shadowfs`

## Example Complete Setup

### 1. Create Configuration

```bash
sudo mkdir -p /etc/shadowfs
sudo cat > /etc/shadowfs/config.yaml <<'EOF'
shadowfs:
  version: "1.0"
  sources:
    - path: /data/documents
  rules:
    - name: "Hide build artifacts"
      type: exclude
      pattern: "**/__pycache__/**"
  cache:
    enabled: true
    max_size_mb: 512
  logging:
    level: INFO
    file: /var/log/shadowfs/shadowfs.log
EOF

sudo chmod 600 /etc/shadowfs/config.yaml
```

### 2. Create Mount Point

```bash
sudo mkdir -p /mnt/shadowfs
```

### 3. Add to fstab

```bash
echo '/data/documents  /mnt/shadowfs  shadowfs  ro,allow_other,config=/etc/shadowfs/config.yaml  0  0' | \
  sudo tee -a /etc/fstab
```

### 4. Test Mount

```bash
sudo mount /mnt/shadowfs
mount | grep shadowfs
ls /mnt/shadowfs
```

### 5. Verify Auto-Mount at Boot

```bash
sudo reboot
# After reboot:
mount | grep shadowfs
```

## Unmounting Before Shutdown

ShadowFS should be automatically unmounted during system shutdown. If issues occur:

```bash
# Create a systemd service for clean unmount
sudo cat > /etc/systemd/system/shadowfs-umount.service <<'EOF'
[Unit]
Description=Unmount ShadowFS filesystems
DefaultDependencies=no
Before=umount.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/true
ExecStop=/bin/sh -c 'mount | grep shadowfs | cut -d" " -f3 | xargs -r umount'

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable shadowfs-umount.service
```

## See Also

- [mount(8)](https://man7.org/linux/man-pages/man8/mount.8.html) - Mount a filesystem
- [fstab(5)](https://man7.org/linux/man-pages/man5/fstab.5.html) - Static information about filesystems
- [fuse(8)](https://man7.org/linux/man-pages/man8/fuse.8.html) - Filesystem in Userspace
- `/etc/fuse.conf` - FUSE configuration file
- ShadowFS documentation: `shadowfs --help`
