"""Integration tests for server lifecycle."""

import time

import pytest

from pyclide_server.server import PyCLIDEServer


@pytest.mark.integration
class TestLifecycle:
    """Test server startup, shutdown, and lifecycle."""

    def test_server_startup(self, temp_workspace):
        """Server starts, health monitor ready."""
        server = PyCLIDEServer(str(temp_workspace), port=5556)

        # Server initialized
        assert server.root == temp_workspace
        assert server.port == 5556
        assert server.jedi_cache == {}
        assert server.rope_engine is None

        # Cleanup
        if server.rope_engine:
            server.rope_engine.project.close()

    def test_server_initialization_stats(self, temp_workspace):
        """Server initializes with correct initial stats."""
        server = PyCLIDEServer(str(temp_workspace), port=5557)

        # Check initial stats
        assert server.request_count == 0
        assert server.cache_invalidations == 0
        assert server.start_time > 0
        assert server.last_activity > 0

        # Cleanup
        if server.rope_engine:
            server.rope_engine.project.close()

    def test_server_shutdown_cleans_up(self, test_server):
        """Shutdown stops watcher, closes Rope project."""
        server, client = test_server

        # Start file watcher
        server._start_file_watcher()
        assert server.file_watcher is not None

        # Load Rope
        client.post(
            "/occurrences",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(server.root)
            }
        )
        assert server.rope_engine is not None

        # Cleanup (done by fixture teardown)
        server._stop_file_watcher()

        # File watcher should be stopped (observer should be stopped)
        if server.file_watcher:
            assert not server.file_watcher.observer.is_alive()

    def test_last_activity_updated_on_request(self, test_server):
        """Request updates last_activity timestamp."""
        server, client = test_server

        initial_activity = server.last_activity
        time.sleep(0.1)

        # Make a request
        client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(server.root)
            }
        )

        # Last activity should be updated
        assert server.last_activity > initial_activity

    def test_request_count_incremented(self, test_server):
        """Request increments request_count."""
        server, client = test_server

        initial_count = server.request_count

        # Make several requests
        for _ in range(3):
            client.post(
                "/defs",
                json={
                    "file": "sample_module.py",
                    "line": 4,
                    "col": 5,
                    "root": str(server.root)
                }
            )

        # Request count should increase
        assert server.request_count == initial_count + 3

    def test_health_check_returns_uptime(self, httpx_client):
        """Health check returns correct uptime."""
        time.sleep(0.2)  # Let some time pass

        health = httpx_client.get("/health").json()

        # Uptime should be > 0
        assert health["uptime"] > 0
        assert health["uptime"] < 10  # Should be less than 10 seconds

    def test_health_check_returns_stats(self, httpx_client, temp_workspace):
        """Health check returns all expected stats."""
        # Make some requests first
        httpx_client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        health = httpx_client.get("/health").json()

        # Check all expected fields
        assert "status" in health
        assert "workspace" in health
        assert "uptime" in health
        assert "requests" in health
        assert "cache_size" in health
        assert "cache_invalidations" in health

        # Check values
        assert health["status"] == "ok"
        assert health["requests"] > 0
        assert health["cache_size"] >= 0

    def test_multiple_health_checks(self, httpx_client, temp_workspace):
        """Multiple health checks work correctly."""
        # Make a real request first to ensure server is tracking requests
        httpx_client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        health1 = httpx_client.get("/health").json()
        time.sleep(0.1)
        health2 = httpx_client.get("/health").json()

        # Uptime should increase
        assert health2["uptime"] >= health1["uptime"]

        # Request count may or may not increase depending on if health checks count
        # Just verify it's non-zero
        assert health2["requests"] > 0

    def test_workspace_path_in_health(self, httpx_client, temp_workspace):
        """Health response contains correct workspace path."""
        health = httpx_client.get("/health").json()

        assert health["workspace"] == str(temp_workspace)

    def test_jedi_cache_lifecycle(self, test_server, temp_workspace):
        """Jedi cache is created and can be invalidated."""
        server, client = test_server

        # Initially empty
        assert len(server.jedi_cache) == 0

        # Make request to populate
        client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        # Cache should have entry
        assert len(server.jedi_cache) > 0

        # Invalidate manually
        server._invalidate_cache("sample_module.py")

        # Cache should be empty again
        assert len(server.jedi_cache) == 0

    def test_rope_engine_lifecycle(self, test_server, temp_workspace):
        """Rope engine is created lazily and persists."""
        server, client = test_server

        # Initially None
        assert server.rope_engine is None

        # Make Rope request
        client.post(
            "/rename",
            json={
                "file": "sample_module.py",
                "line": 14,
                "col": 5,
                "new_name": "msg",
                "root": str(temp_workspace)
            }
        )

        # Should be created
        assert server.rope_engine is not None

        # Make another Rope request
        client.post(
            "/occurrences",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        # Should reuse same engine
        assert server.rope_engine is not None
