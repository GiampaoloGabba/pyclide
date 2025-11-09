# Test Guide for Coding Agents

## Architecture

```
tests/
├── unit/          # Fast, isolated, no HTTP (TestClient not used)
├── integration/   # Server API integration (uses TestClient)
├── client/        # Client local features (list, codemod)
└── e2e/          # Full stack with real server (uses uvx, optional)
```

## Core Fixtures (conftest.py)

**Server Testing:**
- `fixtures_dir` → Path to tests/fixtures/
- `temp_workspace(tmp_path, fixtures_dir)` → Temp dir with fixture files copied
- `test_server(temp_workspace)` → (PyCLIDEServer, TestClient) tuple
- `httpx_client(test_server)` → TestClient for making requests

**E2E Testing:**
- `e2e_workspace(tmp_path, fixtures_dir)` → Temp workspace for E2E
- `temp_registry(tmp_path, monkeypatch)` → Isolated registry, auto-cleanup servers

## Request Patterns

### Integration Test (Server API)
```python
def test_feature(self, httpx_client, temp_workspace):
    response = httpx_client.post("/endpoint", json={
        "file": "sample.py",
        "line": 10,
        "col": 5,
        "root": str(temp_workspace)
    })
    assert response.status_code == 200
    data = response.json()
    assert "expected_field" in data
```

### E2E Test (Real Server)
```python
from pyclide_client import handle_defs

def test_feature(self, e2e_workspace, temp_registry, capsys):
    handle_defs(["sample.py", "10", "5"], str(e2e_workspace))
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "locations" in data
```

### Client Test (Local Feature)
```python
from pyclide_client import handle_list

def test_feature(self, tmp_path, capsys):
    handle_list(["sample.py"], str(tmp_path))
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert len(result) > 0
```

## Markers

Use `@pytest.mark.<marker>`:
- `unit` - Fast isolated tests
- `integration` - Server API tests
- `client` - Client local features
- `e2e` - End-to-end tests (skipped by default)
- `jedi` - Jedi functionality
- `rope` - Rope functionality
- `slow` - Takes >1 second
- `asyncio` - Requires pytest-asyncio

## Naming Conventions

- Test classes: `TestFeatureName`
- Test methods: `test_specific_behavior`
- Fixtures in temp_workspace: Use existing fixtures/sample_*.py
- New test data: Create in method with tmp_path.write_text()

## What to Test

**Unit:** Models, helpers, utilities (no HTTP)
**Integration:** Server endpoints, cache, error handling, workflows
**Client:** Local commands (list, codemod)
**E2E:** Client-server communication, registry, lifecycle

## What NOT to Test

- CLI-specific Typer commands (deprecated)
- Byte offset calculations (internal)
- Atomic file writes (internal)
- JSON formatting (FastAPI handles it)

## Server Response Contracts

**Locations response:**
```python
{"locations": [{"file": str, "line": int, "column": int, ...}]}
```

**Patches response:**
```python
{"patches": {"file_path": "new_content", ...}}
```

**Hover response:**
```python
{"signature": str, "docstring": str, "type": str}
```

## Error Handling

- Invalid file → May return 200 with empty result OR 400/500
- Out of bounds position → Handle gracefully, don't assume error
- Syntax errors → Server should not crash, return 200 with empty/error
- Use try/except in E2E tests (server might fail on edge cases)

## File Paths

- **Integration tests:** Use relative paths (e.g., "sample_module.py")
- **E2E tests:** Use relative paths, client resolves them
- **Root parameter:** Always str(temp_workspace) or str(e2e_workspace)

## Test Organization

- Group related tests in classes
- One class per feature/endpoint
- Order: happy path → edge cases → errors
- Keep test methods under 20 lines
- Use descriptive assertion messages only when non-obvious

## Performance

- Integration tests: ~15-20s total
- E2E tests: ~25-30s total (real server startup)
- Skip E2E by default: `pytest -m "not e2e"`

## Adding New Tests

1. Determine type: unit/integration/client/e2e
2. Use appropriate fixtures
3. Follow existing patterns in that directory
4. Add markers
5. Verify test runs: `pytest tests/<file>::TestClass::test_method -v`
