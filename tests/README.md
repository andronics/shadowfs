# ShadowFS Test Suite

## Test Coverage Requirements

### Phase 0 (Development Infrastructure)
- Coverage requirement: 0% (no production code yet)
- Adjust `pytest.ini` to `--cov-fail-under=0`

### Phase 1+ (Production Code)
- Coverage requirement: 100%
- Adjust `pytest.ini` to `--cov-fail-under=100` before starting Phase 1

## Test Organization

- `foundation/` - Layer 1 component tests
- `infrastructure/` - Layer 2 component tests
- `integration/` - Layer 3 component tests
- `application/` - Layer 4 component tests
- `e2e/` - End-to-end tests
- `conftest.py` - Shared fixtures

## Running Tests

```bash
# All tests
make test

# Unit tests only
make test-unit

# Integration tests
make test-integration

# Coverage report
make test-coverage
```