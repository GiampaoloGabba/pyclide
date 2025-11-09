"""Pytest configuration and shared fixtures."""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient

# Import server components
from pyclide_server.server import PyCLIDEServer


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "jedi: Tests for Jedi integration features")
    config.addinivalue_line("markers", "rope: Tests for Rope refactoring features")
    config.addinivalue_line("markers", "utility: Tests for utility functions")
    config.addinivalue_line("markers", "slow: Tests that take longer to run")
    config.addinivalue_line(
        "markers", "integration: Integration tests that test multiple components"
    )
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (slow, full stack)")
    config.addinivalue_line("markers", "windows: Windows-specific tests")
    config.addinivalue_line("markers", "unix: Unix-specific tests")


@pytest.fixture
def fixtures_dir():
    """Return the fixtures directory path."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_workspace(tmp_path, fixtures_dir):
    """
    Create a temporary workspace with sample Python files.

    Copies all fixture files to a temporary directory for isolated testing.
    """
    # Copy all Python files from fixtures
    for file in fixtures_dir.rglob("*.py"):
        relative_path = file.relative_to(fixtures_dir)
        dest_file = tmp_path / relative_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(file, dest_file)

    return tmp_path


@pytest.fixture
def test_server(temp_workspace):
    """
    Create a test server instance with TestClient.

    Returns a tuple of (server_instance, test_client).
    The server is automatically cleaned up after the test.
    """
    # Create server instance (don't start it, just use the FastAPI app)
    server = PyCLIDEServer(str(temp_workspace), port=5555)

    # Create TestClient for making requests
    client = TestClient(server.app)

    yield server, client

    # Cleanup
    if server.file_watcher:
        server.file_watcher.stop()
    if server.rope_engine:
        server.rope_engine.project.close()


@pytest.fixture
def httpx_client(test_server):
    """
    HTTP client for making requests to the test server.

    Returns the TestClient instance for convenience.
    """
    _, client = test_server
    return client


@pytest.fixture
def sample_files(temp_workspace, fixtures_dir):
    """
    Return dictionary mapping fixture file names to their absolute paths.
    """
    files = {}
    for file in fixtures_dir.rglob("*.py"):
        relative_path = file.relative_to(fixtures_dir)
        files[str(relative_path)] = temp_workspace / relative_path
    return files


@pytest.fixture(scope="session")
def registry_backup(tmp_path_factory):
    """
    Backup and restore ~/.pyclide/servers.json if it exists.

    This prevents test pollution of the user's real registry.
    """
    import os
    from pathlib import Path

    registry_path = Path.home() / ".pyclide" / "servers.json"
    backup_path = None

    if registry_path.exists():
        backup_dir = tmp_path_factory.mktemp("registry_backup")
        backup_path = backup_dir / "servers.json.bak"
        shutil.copy(registry_path, backup_path)

    yield

    # Restore backup if it existed
    if backup_path and backup_path.exists():
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(backup_path, registry_path)
    elif registry_path.exists():
        # Remove test registry if no backup existed
        registry_path.unlink()


@pytest.fixture
def clean_registry(tmp_path):
    """
    Provide a clean temporary registry for testing.

    Sets up a temporary ~/.pyclide/servers.json and cleans up after.
    """
    import os
    from pathlib import Path

    # Use temporary directory for registry
    test_registry = tmp_path / "pyclide_test_registry"
    test_registry.mkdir(parents=True, exist_ok=True)

    # Override registry location (if client supports it)
    # This would need to be implemented in the client code

    yield test_registry

    # Cleanup is automatic with tmp_path
