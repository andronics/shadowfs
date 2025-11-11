.PHONY: help setup test lint format clean docs install dev-install

PYTHON := python3
VENV := venv
BIN := $(VENV)/bin

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Set up development environment
	@bash scripts/setup_dev.sh

install: ## Install production dependencies
	$(BIN)/pip install -e .

dev-install: ## Install development dependencies
	$(BIN)/pip install -e .[dev,transforms,metrics]

test: ## Run all tests with coverage
	$(BIN)/pytest tests/ -v --cov=shadowfs --cov-report=term-missing

test-unit: ## Run unit tests only
	$(BIN)/pytest tests/ -v -m "not integration and not e2e" --cov=shadowfs

test-integration: ## Run integration tests
	$(BIN)/pytest tests/integration/ tests/e2e/ -v -m "integration or e2e"

test-coverage: ## Generate HTML coverage report
	$(BIN)/pytest tests/ --cov=shadowfs --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

lint: ## Run all linting checks
	$(BIN)/black --check shadowfs/ tests/
	$(BIN)/isort --check-only shadowfs/ tests/
	$(BIN)/flake8 shadowfs/ tests/
	$(BIN)/mypy shadowfs/ --strict
	$(BIN)/bandit -r shadowfs/ -ll

format: ## Format code with black and isort
	$(BIN)/black shadowfs/ tests/
	$(BIN)/isort shadowfs/ tests/

security: ## Run security checks
	$(BIN)/bandit -r shadowfs/
	$(BIN)/safety check

clean: ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info
	rm -rf htmlcov/ .coverage* .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

docs: ## Generate documentation
	$(BIN)/sphinx-build -b html docs/ docs/_build/html

pre-commit: ## Run pre-commit hooks on all files
	$(BIN)/pre-commit run --all-files

run: ## Run ShadowFS (development mode)
	$(BIN)/python -m shadowfs.application.shadowfs_main

build: ## Build distribution packages
	$(BIN)/pip install build
	$(BIN)/python -m build

release: ## Create a release (requires confirmation)
	@echo "This will create a new release. Continue? [y/N]"
	@read -r confirm && [ "$$confirm" = "y" ] || exit 1
	@echo "Creating release..."
	$(MAKE) clean
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) build
	@echo "Release artifacts created in dist/"