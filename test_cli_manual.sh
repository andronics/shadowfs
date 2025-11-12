#!/bin/bash
# Manual CLI Testing Script for ShadowFS

set -e

echo "================================"
echo "ShadowFS CLI Manual Test Script"
echo "================================"
echo

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Install in development mode
echo -e "${YELLOW}Test 1: Installing ShadowFS in development mode${NC}"
pip install -e . > /dev/null 2>&1
echo -e "${GREEN}✓ Installed${NC}"
echo

# Test 2: Check if commands are available
echo -e "${YELLOW}Test 2: Checking installed commands${NC}"
if command -v shadowfs &> /dev/null; then
    echo -e "${GREEN}✓ 'shadowfs' command available${NC}"
    which shadowfs
else
    echo "✗ 'shadowfs' command not found"
fi

if command -v shadowfs-ctl &> /dev/null; then
    echo -e "${GREEN}✓ 'shadowfs-ctl' command available${NC}"
    which shadowfs-ctl
else
    echo "✗ 'shadowfs-ctl' command not found"
fi
echo

# Test 3: Version check
echo -e "${YELLOW}Test 3: Version check${NC}"
shadowfs --version
echo

# Test 4: Help output
echo -e "${YELLOW}Test 4: Help output${NC}"
shadowfs --help | head -20
echo "... (truncated)"
echo

# Test 5: Create test directories
echo -e "${YELLOW}Test 5: Setting up test environment${NC}"
TEST_DIR="/tmp/shadowfs-test-$$"
mkdir -p "$TEST_DIR"/{source,mount}

# Create some test files
echo "Hello from test file 1" > "$TEST_DIR/source/file1.txt"
echo "Hello from test file 2" > "$TEST_DIR/source/file2.txt"
mkdir -p "$TEST_DIR/source/subdir"
echo "Nested file" > "$TEST_DIR/source/subdir/nested.txt"

echo -e "${GREEN}✓ Test environment created at: $TEST_DIR${NC}"
ls -la "$TEST_DIR/source"
echo

# Test 6: Dry run with arguments (validation only)
echo -e "${YELLOW}Test 6: Testing argument parsing${NC}"
echo "Command: shadowfs --sources $TEST_DIR/source --mount $TEST_DIR/mount --help"
echo "(This will show help and not actually mount)"
# shadowfs --sources "$TEST_DIR/source" --mount "$TEST_DIR/mount" --help
echo

# Test 7: Show example commands
echo -e "${YELLOW}Test 7: Example commands to try manually${NC}"
echo
echo "# Mount with single source (run in foreground for testing):"
echo "shadowfs --sources $TEST_DIR/source --mount $TEST_DIR/mount --foreground --debug"
echo
echo "# In another terminal, test the mounted filesystem:"
echo "ls -la $TEST_DIR/mount"
echo "cat $TEST_DIR/mount/file1.txt"
echo
echo "# Unmount when done:"
echo "fusermount -u $TEST_DIR/mount  # Linux"
echo "umount $TEST_DIR/mount         # macOS"
echo
echo "# Control commands (while mounted):"
echo "shadowfs-ctl stats"
echo "shadowfs-ctl reload"
echo

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}================================${NC}"
echo
echo "Test environment preserved at: $TEST_DIR"
echo "Clean up when done with: rm -rf $TEST_DIR"
