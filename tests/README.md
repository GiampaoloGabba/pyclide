# PyCLIDE Test Suite

Comprehensive test suite for the PyCLIDE client-server architecture.

## Quick Start

```bash
# Run all core tests (recommended)
pytest tests/ -m "not e2e"

# Run all tests including E2E
pytest tests/

# Run with coverage
pytest tests/ -m "not e2e" --cov=pyclide_server --cov-report=html
```

## Test Organization

The test suite is organized by scope and purpose:

```
tests/
├── unit/          # Fast, isolated unit tests (models, helpers, watchers)
├── integration/   # Server API integration tests (endpoints, workflows, edge cases)
├── client/        # Client-side local feature tests (list, codemod)
├── e2e/          # End-to-end tests (full client-server stack, optional)
├── fixtures/      # Sample Python files for testing
└── conftest.py    # Shared pytest fixtures and configuration
```

### Test Types

**Unit Tests** (~31 tests, <1s)
- Pydantic model validation
- Jedi helper functions
- File watcher behavior
- No HTTP, no server startup

**Integration Tests** (~168 tests, ~15s)
- Server API endpoints
- Cache invalidation
- Error handling
- Multi-file refactoring workflows
- Real-world framework patterns (Django, Flask, FastAPI)

**Client Tests** (~12 tests, <1s)
- Local commands (list, codemod)
- AST-based symbol listing
- ast-grep transformations

**E2E Tests** (~15 tests, ~25s, optional)
- Full client-server communication
- Server lifecycle management
- Registry handling
- Real uvx server startup

## Running Tests

### By Type
```bash
# Fast tests only (unit + integration + client)
pytest -m "not e2e"

# Only E2E tests
pytest -m e2e

# Only unit tests
pytest -m unit

# Only integration tests
pytest -m integration
```

### By Feature
```bash
# Jedi integration tests
pytest -m jedi

# Rope refactoring tests
pytest -m rope

# Client-specific tests
pytest -m client
```

### Specific Tests
```bash
# Run specific file
pytest tests/integration/test_server_api.py

# Run specific class
pytest tests/integration/test_server_api.py::TestServerAPI

# Run specific test
pytest tests/integration/test_server_api.py::TestServerAPI::test_health_endpoint

# Verbose output with traceback
pytest tests/integration/ -v --tb=short
```

## Available Markers

- `unit` - Fast isolated unit tests
- `integration` - Server API integration tests
- `client` - Client local feature tests
- `e2e` - End-to-end tests (optional, slower)
- `jedi` - Jedi navigation features
- `rope` - Rope refactoring features
- `slow` - Tests taking >1 second
- `asyncio` - Async tests (requires pytest-asyncio)

## Key Fixtures

**Server Testing:**
- `temp_workspace` - Temporary directory with fixture files
- `test_server` - PyCLIDEServer instance with TestClient
- `httpx_client` - HTTP client for making API requests

**E2E Testing:**
- `e2e_workspace` - Isolated workspace for E2E tests
- `temp_registry` - Temporary server registry with auto-cleanup

See `conftest.py` for complete fixture definitions.

## Test Coverage

Current coverage: **~88%** (211/226 tests passing)

**Core functionality:** ✅ 100% passing
- Server endpoints (Jedi/Rope integration)
- Cache management
- Error handling
- Client local features

**Skipped tests:**
- 8 HealthMonitor tests (require pytest-asyncio)
- 5 endpoint tests (features not yet implemented)

## Requirements

**Core dependencies:**
```bash
pip install pytest fastapi jedi rope
```

**Optional:**
```bash
pip install pytest-cov        # Coverage reports
pip install pytest-asyncio    # Async tests
pip install ast-grep          # Codemod tests
```

## Writing New Tests

For coding agents, see [`CLAUDE.md`](./CLAUDE.md) for detailed conventions.

For humans:
1. Choose test type: unit, integration, client, or e2e
2. Use existing patterns in that directory
3. Add appropriate markers
4. Use shared fixtures from `conftest.py`
5. Follow naming: `test_*.py`, `TestClassName`, `test_method_name`

## CI/CD

Recommended CI configuration:
```yaml
# Fast tests for PR checks
pytest tests/ -m "not e2e" --cov --cov-report=xml

# Full tests for merge
pytest tests/ --cov --cov-report=xml
```

E2E tests can be optional in CI due to:
- Longer execution time (~25s)
- Real server startup requirements
- Potential platform-specific issues

## Troubleshooting

**Tests fail with "Server communication failed":**
- E2E tests require `uvx` installed
- Check if ports 5000-5100 are available
- Run with `-v` for detailed output

**Import errors:**
- Ensure pytest runs from project root
- Check that dependencies are installed
- Verify virtual environment is activated

**Slow test execution:**
- Skip E2E tests: `pytest -m "not e2e"`
- Run specific test categories
- Use `-n auto` with pytest-xdist for parallel execution

## Architecture Notes

This test suite validates the **client-server architecture**:
- **Server** (pyclide-server): FastAPI server with Jedi/Rope integration
- **Client** (pyclide_client.py): Python client managing server lifecycle
- **Local features**: AST parsing and ast-grep run client-side

Integration tests use FastAPI's `TestClient` for synchronous HTTP testing without starting real servers. E2E tests use the actual client and spawn real servers via `uvx`.
