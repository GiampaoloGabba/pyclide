"""Comprehensive unit tests for client registry functions.

The registry manages server instances across workspaces.
Critical for server lifecycle management.
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Import client
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pyclide"))
from pyclide_client import (
    get_registry_path,
    load_registry,
    save_registry,
    find_server,
    add_server,
    remove_server
)


@pytest.mark.client
@pytest.mark.unit
class TestGetRegistryPath:
    """Test get_registry_path() function."""

    def test_registry_path_in_home_dir(self):
        """Registry path is in home directory."""
        path = get_registry_path()

        assert path.name == "servers.json"
        assert path.parent.name == ".pyclide"
        # Should be absolute path
        assert path.is_absolute()

    def test_registry_path_contains_home(self):
        """Registry path contains user home directory."""
        path = get_registry_path()

        # Should be under home directory
        assert Path.home() in path.parents

    def test_registry_path_returns_path_object(self):
        """get_registry_path() returns Path object."""
        path = get_registry_path()

        assert isinstance(path, Path)


@pytest.mark.client
@pytest.mark.unit
class TestLoadRegistry:
    """Test load_registry() function."""

    def test_load_nonexistent_registry_returns_empty(self, tmp_path, monkeypatch):
        """load_registry() returns empty structure if file doesn't exist."""
        # Mock registry path to temp location
        fake_registry = tmp_path / "nonexistent" / "servers.json"
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: fake_registry)

        result = load_registry()

        assert result == {"servers": []}

    def test_load_existing_registry(self, tmp_path, monkeypatch):
        """load_registry() loads existing registry file."""
        # Create registry file
        registry_file = tmp_path / "servers.json"
        registry_data = {
            "servers": [
                {"workspace_root": "/path/to/workspace", "port": 8000}
            ]
        }
        registry_file.write_text(json.dumps(registry_data), encoding="utf-8")

        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        result = load_registry()

        assert result == registry_data
        assert len(result["servers"]) == 1
        assert result["servers"][0]["port"] == 8000

    def test_load_registry_with_multiple_servers(self, tmp_path, monkeypatch):
        """load_registry() handles multiple servers."""
        registry_file = tmp_path / "servers.json"
        registry_data = {
            "servers": [
                {"workspace_root": "/workspace1", "port": 8000, "started_at": 123.45},
                {"workspace_root": "/workspace2", "port": 8001, "started_at": 678.90},
                {"workspace_root": "/workspace3", "port": 8002, "started_at": 999.99}
            ]
        }
        registry_file.write_text(json.dumps(registry_data), encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        result = load_registry()

        assert len(result["servers"]) == 3

    def test_load_registry_empty_servers_list(self, tmp_path, monkeypatch):
        """load_registry() handles empty servers list."""
        registry_file = tmp_path / "servers.json"
        registry_file.write_text('{"servers": []}', encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        result = load_registry()

        assert result == {"servers": []}

    def test_load_registry_malformed_json(self, tmp_path, monkeypatch):
        """load_registry() raises on malformed JSON."""
        registry_file = tmp_path / "servers.json"
        registry_file.write_text("{invalid json", encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        with pytest.raises(json.JSONDecodeError):
            load_registry()


@pytest.mark.client
@pytest.mark.unit
class TestSaveRegistry:
    """Test save_registry() function."""

    def test_save_registry_creates_parent_dir(self, tmp_path, monkeypatch):
        """save_registry() creates parent directory if it doesn't exist."""
        registry_file = tmp_path / "new_dir" / "servers.json"
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        data = {"servers": []}
        save_registry(data)

        assert registry_file.exists()
        assert registry_file.parent.exists()

    def test_save_registry_writes_json(self, tmp_path, monkeypatch):
        """save_registry() writes JSON correctly."""
        registry_file = tmp_path / "servers.json"
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        data = {
            "servers": [
                {"workspace_root": "/test", "port": 9000, "started_at": 123.0}
            ]
        }
        save_registry(data)

        # Read and verify
        saved_data = json.loads(registry_file.read_text(encoding="utf-8"))
        assert saved_data == data

    def test_save_registry_overwrites_existing(self, tmp_path, monkeypatch):
        """save_registry() overwrites existing file."""
        registry_file = tmp_path / "servers.json"
        registry_file.write_text('{"servers": [{"old": "data"}]}', encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        new_data = {"servers": [{"new": "data"}]}
        save_registry(new_data)

        saved_data = json.loads(registry_file.read_text(encoding="utf-8"))
        assert saved_data == new_data
        assert "old" not in str(saved_data)

    def test_save_registry_formats_with_indent(self, tmp_path, monkeypatch):
        """save_registry() formats JSON with indentation."""
        registry_file = tmp_path / "servers.json"
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        data = {"servers": [{"workspace_root": "/test", "port": 8000}]}
        save_registry(data)

        content = registry_file.read_text(encoding="utf-8")
        # Should be indented (multiple lines)
        assert "\n" in content
        assert "  " in content  # Has indentation


@pytest.mark.client
@pytest.mark.unit
class TestFindServer:
    """Test find_server() function."""

    def test_find_server_exists(self, tmp_path, monkeypatch):
        """find_server() returns server if it exists."""
        registry_file = tmp_path / "servers.json"
        workspace = tmp_path / "project"
        workspace.mkdir()

        registry_data = {
            "servers": [
                {"workspace_root": str(workspace.resolve()), "port": 8000}
            ]
        }
        registry_file.write_text(json.dumps(registry_data), encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        result = find_server(str(workspace))

        assert result is not None
        assert result["port"] == 8000
        assert result["workspace_root"] == str(workspace.resolve())

    def test_find_server_not_exists(self, tmp_path, monkeypatch):
        """find_server() returns None if server doesn't exist."""
        registry_file = tmp_path / "servers.json"
        registry_file.write_text('{"servers": []}', encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        result = find_server("/nonexistent/workspace")

        assert result is None

    def test_find_server_resolves_path(self, tmp_path, monkeypatch):
        """find_server() resolves relative paths."""
        registry_file = tmp_path / "servers.json"
        workspace = tmp_path / "project"
        workspace.mkdir()

        registry_data = {
            "servers": [
                {"workspace_root": str(workspace.resolve()), "port": 8000}
            ]
        }
        registry_file.write_text(json.dumps(registry_data), encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        # Change to parent directory and use relative path
        monkeypatch.chdir(workspace.parent)
        result = find_server("project")

        assert result is not None
        assert result["port"] == 8000

    def test_find_server_multiple_servers(self, tmp_path, monkeypatch):
        """find_server() finds correct server among multiple."""
        registry_file = tmp_path / "servers.json"

        workspace1 = tmp_path / "workspace1"
        workspace2 = tmp_path / "workspace2"
        workspace3 = tmp_path / "workspace3"
        workspace1.mkdir()
        workspace2.mkdir()
        workspace3.mkdir()

        registry_data = {
            "servers": [
                {"workspace_root": str(workspace1.resolve()), "port": 8000},
                {"workspace_root": str(workspace2.resolve()), "port": 8001},
                {"workspace_root": str(workspace3.resolve()), "port": 8002}
            ]
        }
        registry_file.write_text(json.dumps(registry_data), encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        result = find_server(str(workspace2))

        assert result is not None
        assert result["port"] == 8001


@pytest.mark.client
@pytest.mark.unit
class TestAddServer:
    """Test add_server() function."""

    def test_add_server_to_empty_registry(self, tmp_path, monkeypatch):
        """add_server() adds server to empty registry."""
        registry_file = tmp_path / "servers.json"
        registry_file.write_text('{"servers": []}', encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        workspace = tmp_path / "project"
        workspace.mkdir()

        add_server(str(workspace), 8000)

        # Verify registry was updated
        registry = json.loads(registry_file.read_text(encoding="utf-8"))
        assert len(registry["servers"]) == 1
        assert registry["servers"][0]["workspace_root"] == str(workspace.resolve())
        assert registry["servers"][0]["port"] == 8000
        assert "started_at" in registry["servers"][0]

    def test_add_server_to_existing_registry(self, tmp_path, monkeypatch):
        """add_server() appends to existing servers."""
        registry_file = tmp_path / "servers.json"

        existing_workspace = tmp_path / "existing"
        existing_workspace.mkdir()

        registry_data = {
            "servers": [
                {"workspace_root": str(existing_workspace.resolve()), "port": 7999, "started_at": 100.0}
            ]
        }
        registry_file.write_text(json.dumps(registry_data), encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        new_workspace = tmp_path / "new_project"
        new_workspace.mkdir()

        add_server(str(new_workspace), 8000)

        registry = json.loads(registry_file.read_text(encoding="utf-8"))
        assert len(registry["servers"]) == 2
        # Old server still there
        assert any(s["port"] == 7999 for s in registry["servers"])
        # New server added
        assert any(s["port"] == 8000 for s in registry["servers"])

    def test_add_server_resolves_path(self, tmp_path, monkeypatch):
        """add_server() resolves path to absolute."""
        registry_file = tmp_path / "servers.json"
        registry_file.write_text('{"servers": []}', encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        workspace = tmp_path / "project"
        workspace.mkdir()

        # Pass relative path
        add_server("project", 8000)

        registry = json.loads(registry_file.read_text(encoding="utf-8"))
        # Should be absolute
        assert Path(registry["servers"][0]["workspace_root"]).is_absolute()

    def test_add_server_includes_timestamp(self, tmp_path, monkeypatch):
        """add_server() includes started_at timestamp."""
        registry_file = tmp_path / "servers.json"
        registry_file.write_text('{"servers": []}', encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        workspace = tmp_path / "project"
        workspace.mkdir()

        import time
        before = time.time()
        add_server(str(workspace), 8000)
        after = time.time()

        registry = json.loads(registry_file.read_text(encoding="utf-8"))
        timestamp = registry["servers"][0]["started_at"]

        assert before <= timestamp <= after


@pytest.mark.client
@pytest.mark.unit
class TestRemoveServer:
    """Test remove_server() function."""

    def test_remove_server_existing(self, tmp_path, monkeypatch):
        """remove_server() removes existing server."""
        registry_file = tmp_path / "servers.json"

        workspace = tmp_path / "project"
        workspace.mkdir()

        registry_data = {
            "servers": [
                {"workspace_root": str(workspace.resolve()), "port": 8000, "started_at": 100.0}
            ]
        }
        registry_file.write_text(json.dumps(registry_data), encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        remove_server(str(workspace))

        registry = json.loads(registry_file.read_text(encoding="utf-8"))
        assert len(registry["servers"]) == 0

    def test_remove_server_nonexistent(self, tmp_path, monkeypatch):
        """remove_server() handles nonexistent server gracefully."""
        registry_file = tmp_path / "servers.json"
        registry_file.write_text('{"servers": []}', encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        # Should not raise
        remove_server("/nonexistent/workspace")

        registry = json.loads(registry_file.read_text(encoding="utf-8"))
        assert registry["servers"] == []

    def test_remove_server_keeps_others(self, tmp_path, monkeypatch):
        """remove_server() only removes specified server."""
        registry_file = tmp_path / "servers.json"

        workspace1 = tmp_path / "workspace1"
        workspace2 = tmp_path / "workspace2"
        workspace3 = tmp_path / "workspace3"
        workspace1.mkdir()
        workspace2.mkdir()
        workspace3.mkdir()

        registry_data = {
            "servers": [
                {"workspace_root": str(workspace1.resolve()), "port": 8000},
                {"workspace_root": str(workspace2.resolve()), "port": 8001},
                {"workspace_root": str(workspace3.resolve()), "port": 8002}
            ]
        }
        registry_file.write_text(json.dumps(registry_data), encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        remove_server(str(workspace2))

        registry = json.loads(registry_file.read_text(encoding="utf-8"))
        assert len(registry["servers"]) == 2
        # workspace1 and workspace3 still there
        ports = {s["port"] for s in registry["servers"]}
        assert 8000 in ports
        assert 8002 in ports
        assert 8001 not in ports

    def test_remove_server_resolves_path(self, tmp_path, monkeypatch):
        """remove_server() resolves path before matching."""
        registry_file = tmp_path / "servers.json"

        workspace = tmp_path / "project"
        workspace.mkdir()

        registry_data = {
            "servers": [
                {"workspace_root": str(workspace.resolve()), "port": 8000}
            ]
        }
        registry_file.write_text(json.dumps(registry_data), encoding="utf-8")
        monkeypatch.setattr("pyclide_client.get_registry_path", lambda: registry_file)

        # Change to parent directory and use relative path
        monkeypatch.chdir(workspace.parent)
        remove_server("project")

        registry = json.loads(registry_file.read_text(encoding="utf-8"))
        assert len(registry["servers"]) == 0
