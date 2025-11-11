#!/bin/bash
set -euo pipefail

echo "🚀 Setting up ShadowFS development environment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1-2)
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Error: Python $REQUIRED_VERSION or higher required (found $PYTHON_VERSION)${NC}"
    exit 1
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip wheel setuptools

# Install dependencies
echo "Installing dependencies..."
pip install -e .[dev,transforms,metrics]

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install || echo "Pre-commit hooks installation skipped"

# Run initial checks
echo -e "\n${GREEN}Running initial checks...${NC}"
black --version && echo "✓ Black installed"
flake8 --version && echo "✓ Flake8 installed"
mypy --version && echo "✓ MyPy installed"
pytest --version && echo "✓ Pytest installed"

# Format code
echo -e "\n${GREEN}Formatting code...${NC}"
black shadowfs/ tests/ 2>/dev/null || echo "No Python files to format yet"
isort shadowfs/ tests/ 2>/dev/null || echo "No Python files to sort imports yet"

# Run tests
echo -e "\n${GREEN}Running tests...${NC}"
pytest tests/ -v --co 2>/dev/null || echo "No tests found yet (this is expected in Phase 0)"

echo -e "\n${GREEN}✅ Development environment setup complete!${NC}"
echo -e "${YELLOW}To activate the environment in the future, run: source venv/bin/activate${NC}"
echo -e "${YELLOW}To run tests, use: make test${NC}"
echo -e "${YELLOW}To check code quality, use: make lint${NC}"