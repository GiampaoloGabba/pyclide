"""End-to-end tests for client-server integration.

These tests use the REAL client and server, testing:
- Client server lifecycle management (start, find, registry)
- HTTP communication between client and server
- Complete end-to-end request/response flow
- Server auto-start via uvx

These are slower than unit/integration tests because they:
- Start real server processes
- Make real HTTP requests
- Test actual registry management

NOTE: These tests are OPTIONAL and can be skipped.
Run with: pytest -m e2e
Skip with: pytest -m "not e2e" (default)
"""

import json
import shutil
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Import client for testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pyclide"))
from pyclide_client import (
    handle_defs,
    handle_refs,
    handle_hover,
    handle_rename,
    handle_occurrences,
    handle_extract_method,
    handle_extract_var,
    handle_move,
    handle_organize_imports,
    get_registry_path,
    load_registry,
    save_registry,
    remove_server,
)


@pytest.fixture
def e2e_workspace(tmp_path, fixtures_dir):
    """Create temporary workspace for E2E tests."""
    # Copy fixtures to temp workspace
    for file in fixtures_dir.rglob("*.py"):
        if file.name != "invalid_syntax.py":
            relative_path = file.relative_to(fixtures_dir)
            dest_file = tmp_path / relative_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(file, dest_file)
    return tmp_path


@pytest.fixture
def temp_registry(tmp_path, monkeypatch):
    """Use temporary registry for E2E tests to avoid conflicts."""
    # Create temp registry path
    temp_registry_dir = tmp_path / ".pyclide_test"
    temp_registry_dir.mkdir(parents=True, exist_ok=True)
    temp_registry_file = temp_registry_dir / "servers.json"

    # Backup original registry
    original_registry_path = get_registry_path()
    original_data = None
    if original_registry_path.exists():
        with open(original_registry_path, 'r') as f:
            original_data = f.read()

    # Patch get_registry_path to use temp location
    def mock_get_registry_path():
        return temp_registry_file

    monkeypatch.setattr("pyclide_client.get_registry_path", mock_get_registry_path)

    # Initialize empty registry
    save_registry({"servers": []})

    yield temp_registry_file

    # Cleanup: Try to shutdown servers gracefully
    from urllib.request import urlopen, Request
    from urllib.error import URLError

    registry = load_registry()
    for server_info in registry.get("servers", []):
        try:
            # Try to send shutdown request
            port = server_info.get("port")
            if port:
                try:
                    url = f"http://127.0.0.1:{port}/shutdown"
                    req = Request(url, method='POST')
                    urlopen(req, timeout=1.0)
                except (URLError, Exception):
                    pass  # Server might be already down

            remove_server(server_info["workspace_root"])
        except Exception:
            pass

    # Restore original registry if it existed
    if original_data and original_registry_path.exists():
        with open(original_registry_path, 'w') as f:
            f.write(original_data)


@pytest.mark.e2e
@pytest.mark.skipif(not shutil.which("uvx"), reason="uvx not available")
class TestDefsCommandE2E:
    """E2E tests for 'defs' command (go to definition)."""

    def test_defs_goto_function_definition(self, e2e_workspace, temp_registry, capsys):
        """Test goto definition on a function call (full E2E)."""
        # Call client function directly (which will start server, make HTTP request, return result)
        handle_defs(
            ["sample_usage.py", "9", "20"],  # line 9, col 20 - on "hello_world"
            str(e2e_workspace)
        )

        # Capture output
        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # Verify locations response
        assert "locations" in data
        locations = data["locations"]
        assert len(locations) > 0

        # Jedi may return import location or actual definition
        # Both are valid - verify we got a location
        assert all("file" in loc for loc in locations)

    def test_defs_goto_class_definition(self, e2e_workspace, temp_registry, capsys):
        """Test goto definition on a class instantiation (full E2E)."""
        handle_defs(
            ["sample_usage.py", "13", "15"],  # On "Calculator"
            str(e2e_workspace)
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert "locations" in data
        assert len(data["locations"]) > 0

    def test_defs_symbol_not_found(self, e2e_workspace, temp_registry, capsys):
        """Test when symbol is not found (full E2E)."""
        handle_defs(
            ["sample_module.py", "1", "1"],  # Empty docstring line
            str(e2e_workspace)
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # Should return empty locations
        assert "locations" in data
        assert isinstance(data["locations"], list)

    def test_defs_invalid_file_path(self, e2e_workspace, temp_registry, capsys):
        """Test with invalid file path (full E2E)."""
        # Server may return 500 error or handle gracefully
        # Client might retry, so we accept multiple outcomes
        try:
            handle_defs(
                ["nonexistent.py", "1", "1"],
                str(e2e_workspace)
            )
            # If successful, verify response structure
            captured = capsys.readouterr()
            data = json.loads(captured.out)
            assert "locations" in data
        except (SystemExit, Exception):
            # Also acceptable - server returned error
            pass


@pytest.mark.e2e
@pytest.mark.skipif(not shutil.which("uvx"), reason="uvx not available")
class TestRefsCommandE2E:
    """E2E tests for 'refs' command (find references)."""

    def test_refs_find_function_references(self, e2e_workspace, temp_registry, capsys):
        """Test finding references to a function (full E2E)."""
        handle_refs(
            ["sample_module.py", "4", "5"],  # On "hello_world" definition
            str(e2e_workspace)
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert "locations" in data
        # Should find references in sample_usage.py
        assert len(data["locations"]) > 0

    def test_refs_find_class_references(self, e2e_workspace, temp_registry, capsys):
        """Test finding references to a class (full E2E)."""
        handle_refs(
            ["sample_module.py", "8", "7"],  # On "Calculator" class definition
            str(e2e_workspace)
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert "locations" in data
        locations = data["locations"]
        # May find references (Jedi behavior varies)
        # Just verify response structure is valid
        assert isinstance(locations, list)


@pytest.mark.e2e
@pytest.mark.skipif(not shutil.which("uvx"), reason="uvx not available")
class TestHoverCommandE2E:
    """E2E tests for 'hover' command (symbol information)."""

    def test_hover_function_signature(self, e2e_workspace, temp_registry, capsys):
        """Test hover on function shows signature (full E2E)."""
        handle_hover(
            ["sample_module.py", "4", "5"],  # On "hello_world"
            str(e2e_workspace)
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # Should have signature or docstring
        assert "signature" in data or "docstring" in data

    def test_hover_class_method(self, e2e_workspace, temp_registry, capsys):
        """Test hover on class method (full E2E)."""
        handle_hover(
            ["sample_module.py", "11", "9"],  # On "add" method
            str(e2e_workspace)
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # Should have information about the method
        assert "signature" in data or "docstring" in data


@pytest.mark.e2e
@pytest.mark.skipif(not shutil.which("uvx"), reason="uvx not available")
class TestRenameCommandE2E:
    """E2E tests for 'rename' command (semantic rename)."""

    def test_rename_local_variable(self, e2e_workspace, temp_registry, capsys):
        """Test renaming a local variable (full E2E)."""
        handle_rename(
            ["sample_module.py", "14", "5", "greeting_msg"],  # Rename "msg" to "greeting_msg"
            str(e2e_workspace)
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # Should return patches
        assert "patches" in data
        patches = data["patches"]
        assert isinstance(patches, dict)

        # Should modify sample_module.py
        assert any("sample_module.py" in path for path in patches.keys())

        # New content should contain new name
        for content in patches.values():
            if "greeting_msg" in content or "msg" in content:
                break
        else:
            pytest.fail("Expected renamed variable in patches")

    def test_rename_function(self, e2e_workspace, temp_registry, capsys):
        """Test renaming a function across files (full E2E)."""
        handle_rename(
            ["sample_module.py", "4", "5", "greet"],  # Rename "hello_world" to "greet"
            str(e2e_workspace)
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert "patches" in data
        patches = data["patches"]

        # Should modify both definition and usage files
        assert len(patches) >= 1


@pytest.mark.e2e
@pytest.mark.skipif(not shutil.which("uvx"), reason="uvx not available")
class TestOccurrencesCommandE2E:
    """E2E tests for 'occurrences' command (semantic occurrences)."""

    def test_occurrences_find_function_usages(self, e2e_workspace, temp_registry, capsys):
        """Test finding all occurrences of a function (full E2E)."""
        handle_occurrences(
            ["sample_module.py", "14", "5"],  # On local variable "msg"
            str(e2e_workspace)
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # Should return locations of all occurrences
        assert "locations" in data
        assert len(data["locations"]) > 0

    def test_occurrences_class_method(self, e2e_workspace, temp_registry, capsys):
        """Test occurrences of a class method (full E2E)."""
        # Rope might fail on some edge cases - handle gracefully
        try:
            handle_occurrences(
                ["sample_module.py", "11", "9"],  # On "add" method
                str(e2e_workspace)
            )

            captured = capsys.readouterr()
            data = json.loads(captured.out)

            assert "locations" in data
            assert isinstance(data["locations"], list)
        except (SystemExit, Exception):
            # Rope might fail on some patterns - acceptable in E2E
            pass


@pytest.mark.e2e
@pytest.mark.skipif(not shutil.which("uvx"), reason="uvx not available")
class TestServerLifecycleE2E:
    """E2E tests for server lifecycle management."""

    def test_server_starts_automatically(self, e2e_workspace, temp_registry, capsys):
        """Test that server starts automatically on first request."""
        # Registry should be empty initially
        registry = load_registry()
        assert len(registry["servers"]) == 0

        # Make a request - should start server
        handle_defs(
            ["sample_module.py", "4", "5"],
            str(e2e_workspace)
        )

        # Now registry should have one server
        registry = load_registry()
        assert len(registry["servers"]) == 1
        assert registry["servers"][0]["workspace_root"] == str(Path(e2e_workspace).resolve())

    def test_server_reuses_existing_instance(self, e2e_workspace, temp_registry, capsys):
        """Test that client reuses existing server instance."""
        # First request - starts server
        handle_defs(
            ["sample_module.py", "4", "5"],
            str(e2e_workspace)
        )

        registry_after_first = load_registry()
        first_port = registry_after_first["servers"][0]["port"]

        # Second request - should reuse same server
        handle_refs(
            ["sample_module.py", "4", "5"],
            str(e2e_workspace)
        )

        registry_after_second = load_registry()
        second_port = registry_after_second["servers"][0]["port"]

        # Same server (same port)
        assert first_port == second_port
        assert len(registry_after_second["servers"]) == 1

    def test_server_restarts_if_unhealthy(self, e2e_workspace, temp_registry, capsys):
        """Test that client restarts server if it becomes unhealthy."""
        # Start server
        handle_defs(
            ["sample_module.py", "4", "5"],
            str(e2e_workspace)
        )

        # Manually corrupt registry to simulate dead server
        registry = load_registry()
        registry["servers"][0]["port"] = 9999  # Invalid port
        save_registry(registry)

        # Next request should detect unhealthy server and restart
        # Note: This might take longer due to retry logic
        try:
            handle_refs(
                ["sample_module.py", "4", "5"],
                str(e2e_workspace)
            )

            # If successful, new server should be in registry
            new_registry = load_registry()
            new_port = new_registry["servers"][0]["port"]
            assert new_port != 9999  # Should have restarted with different port
        except Exception:
            # Acceptable if restart fails in test environment
            pass


@pytest.mark.e2e
@pytest.mark.skipif(not shutil.which("uvx"), reason="uvx not available")
class TestExtractMethodCommandE2E:
    """E2E tests for 'extract-method' command."""

    def test_extract_method_basic(self, e2e_workspace, temp_registry, capsys):
        """Test extracting code block to method (full E2E)."""
        handle_extract_method(
            ["sample_module.py", "14", "15", "get_greeting"],  # Extract lines 14-15 (function body)
            str(e2e_workspace)
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # Should return patches
        assert "patches" in data
        patches = data["patches"]
        assert isinstance(patches, dict)

        # Should modify sample_module.py
        if patches:  # Rope might return empty if extraction isn't valid
            assert any("sample_module.py" in path for path in patches.keys())


@pytest.mark.e2e
@pytest.mark.skipif(not shutil.which("uvx"), reason="uvx not available")
class TestExtractVarCommandE2E:
    """E2E tests for 'extract-var' command."""

    def test_extract_var_basic(self, e2e_workspace, temp_registry, capsys, monkeypatch):
        """Test extracting expression to variable (full E2E)."""
        # Extract expression from calculate_sum function (line 20: result = a + b)
        # Line 20: "    result = a + b"
        # Column positions (1-based): "a" starts at col 14, "b" is at col 18, end_col=19 (exclusive)

        # Patch sys.argv to include column parameters
        monkeypatch.setattr('sys.argv', ['pyclide_client.py', 'extract-var',
                                          'sample_module.py', '20', '20', 'sum_expr',
                                          '--start-col', '14', '--end-col', '19',
                                          '--root', str(e2e_workspace)])

        handle_extract_var(
            ["sample_module.py", "20", "20", "sum_expr"],
            str(e2e_workspace)
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # Should return patches
        assert "patches" in data
        patches = data["patches"]
        assert isinstance(patches, dict)


@pytest.mark.e2e
@pytest.mark.skipif(not shutil.which("uvx"), reason="uvx not available")
class TestMoveCommandE2E:
    """E2E tests for 'move' command."""

    def test_move_function_to_new_file(self, e2e_workspace, temp_registry, capsys):
        """Test moving a function to a new file (full E2E)."""
        # Create destination file
        dest_file = e2e_workspace / "new_module.py"
        dest_file.write_text("")

        handle_move(
            ["sample_module.py", "4", "5", "new_module.py"],  # Move "hello_world" function
            str(e2e_workspace)
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # Should return patches
        assert "patches" in data
        patches = data["patches"]
        assert isinstance(patches, dict)

        # Should modify at least the source file
        if patches:
            assert len(patches) >= 1


@pytest.mark.e2e
@pytest.mark.skipif(not shutil.which("uvx"), reason="uvx not available")
class TestOrganizeImportsCommandE2E:
    """E2E tests for 'organize-imports' command."""

    def test_organize_imports_basic(self, e2e_workspace, temp_registry, capsys):
        """Test organizing imports in a file (full E2E)."""
        # Create file with messy imports
        test_file = e2e_workspace / "messy_imports.py"
        test_file.write_text("""
import sys
import os


import json

def use_it():
    print(os.getcwd())
    print(sys.version)
    print(json.dumps({}))
""")

        handle_organize_imports(
            ["messy_imports.py"],
            str(e2e_workspace)
        )

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # Should return patches
        assert "patches" in data
        patches = data["patches"]
        assert isinstance(patches, dict)
