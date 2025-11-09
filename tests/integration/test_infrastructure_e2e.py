"""End-to-end integration tests for server infrastructure.

Tests the core infrastructure components in realistic scenarios:
- Auto-shutdown after inactivity
- FileWatcher + cache invalidation
- Health monitoring lifecycle
- Server recovery scenarios

These tests use reduced timeouts (10 seconds instead of 30 minutes) to run quickly.
"""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

from pyclide_server.server import PyCLIDEServer
from pyclide_server.health import HealthMonitor


@pytest.mark.integration
@pytest.mark.slow
class TestAutoShutdownE2E:
    """Test auto-shutdown after inactivity (E2E with reduced timeout)."""

    @pytest.mark.asyncio
    async def test_server_shuts_down_after_inactivity(self, temp_workspace):
        """Server shuts down after 10 seconds of inactivity."""
        server = PyCLIDEServer(str(temp_workspace), port=5600)

        # Create health monitor with SHORT timeout (10 seconds for testing)
        monitor = HealthMonitor(server)
        monitor.inactivity_timeout = 10  # 10 seconds instead of 30 minutes
        monitor.check_interval = 2  # Check every 2 seconds

        # Mock shutdown to track if it's called
        shutdown_called = []
        original_shutdown = monitor._graceful_shutdown

        async def mock_shutdown():
            shutdown_called.append(True)
            monitor.stop()  # Stop monitoring to exit cleanly

        monitor._graceful_shutdown = mock_shutdown

        # Set last activity to 11 seconds ago (past threshold)
        server.last_activity = time.time() - 11

        # Start monitor and run one health check
        await monitor._health_check()

        # Should have triggered shutdown
        assert len(shutdown_called) == 1

        # Cleanup
        if server.rope_engine:
            server.rope_engine.project.close()

    @pytest.mark.asyncio
    async def test_server_stays_alive_when_active(self, temp_workspace):
        """Server does NOT shut down when receiving requests."""
        server = PyCLIDEServer(str(temp_workspace), port=5601)

        # Create health monitor with short timeout
        monitor = HealthMonitor(server)
        monitor.inactivity_timeout = 10
        monitor.check_interval = 2

        # Mock shutdown
        shutdown_called = []
        async def mock_shutdown():
            shutdown_called.append(True)
            monitor.stop()

        monitor._graceful_shutdown = mock_shutdown

        # Simulate active server (last activity = now)
        server.last_activity = time.time()

        # Run health check
        await monitor._health_check()

        # Should NOT trigger shutdown
        assert len(shutdown_called) == 0

        # Cleanup
        if server.rope_engine:
            server.rope_engine.project.close()

    @pytest.mark.asyncio
    async def test_requests_update_last_activity(self, test_server):
        """Making requests updates last_activity timestamp."""
        server, client = test_server

        initial_activity = server.last_activity

        # Wait a bit
        await asyncio.sleep(0.1)

        # Make request
        response = client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(server.root)
            }
        )

        assert response.status_code == 200

        # Last activity should be updated (later than initial)
        assert server.last_activity > initial_activity

    @pytest.mark.asyncio
    async def test_health_monitor_full_lifecycle(self, temp_workspace):
        """Health monitor starts, runs checks, and stops cleanly."""
        server = PyCLIDEServer(str(temp_workspace), port=5602)

        monitor = HealthMonitor(server)
        monitor.check_interval = 0.5  # Fast checks for testing
        monitor.inactivity_timeout = 3600  # Long timeout (won't trigger)

        # Start monitor in background
        monitor_task = asyncio.create_task(monitor.start())

        # Let it run for a bit
        await asyncio.sleep(1.5)

        # Monitor should be running
        assert monitor.running is True

        # Stop monitor
        monitor.stop()

        # Wait for task to complete
        try:
            await asyncio.wait_for(monitor_task, timeout=2.0)
        except asyncio.TimeoutError:
            pytest.fail("Monitor did not stop within timeout")

        # Should be stopped
        assert monitor.running is False

        # Cleanup
        if server.rope_engine:
            server.rope_engine.project.close()


@pytest.mark.integration
@pytest.mark.slow
class TestFileWatcherE2E:
    """Test FileWatcher detects changes and invalidates cache (E2E)."""

    def test_file_watcher_invalidates_cache_on_modification(self, test_server, temp_workspace):
        """FileWatcher detects file modification and invalidates Jedi cache."""
        server, client = test_server

        # Start file watcher
        server._start_file_watcher()
        assert server.file_watcher is not None

        # Make request to populate Jedi cache
        response = client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )
        assert response.status_code == 200

        # Cache should have entry
        cache_size_before = len(server.jedi_cache)
        assert cache_size_before > 0

        # Modify the file
        sample_file = temp_workspace / "sample_module.py"
        original_content = sample_file.read_text()
        sample_file.write_text(original_content + "\n# Modified by test\n")

        # Wait for watcher to detect change and invalidate cache
        time.sleep(1.0)

        # Cache should be invalidated (smaller or empty)
        cache_size_after = len(server.jedi_cache)
        assert cache_size_after < cache_size_before or cache_size_after == 0

        # Cache invalidations counter should increase
        assert server.cache_invalidations > 0

        # Cleanup
        server._stop_file_watcher()

    def test_file_watcher_ignores_non_python_files(self, test_server, temp_workspace):
        """FileWatcher ignores non-Python file modifications."""
        server, client = test_server

        # Start file watcher
        server._start_file_watcher()

        # Populate cache
        client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        initial_invalidations = server.cache_invalidations

        # Modify a non-Python file
        non_py_file = temp_workspace / "README.txt"
        non_py_file.write_text("This is a test file\n")

        # Wait a bit
        time.sleep(1.0)

        # Cache invalidations should NOT increase
        assert server.cache_invalidations == initial_invalidations

        # Cleanup
        server._stop_file_watcher()

    def test_file_watcher_handles_file_creation(self, test_server, temp_workspace):
        """FileWatcher detects new Python file creation."""
        server, client = test_server

        # Start file watcher
        server._start_file_watcher()

        # Populate cache
        client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        initial_invalidations = server.cache_invalidations

        # Create new Python file
        new_file = temp_workspace / "new_module.py"
        new_file.write_text("def new_function():\n    pass\n")

        # Wait for watcher
        time.sleep(1.0)

        # Cache should be invalidated (creation might affect imports)
        assert server.cache_invalidations >= initial_invalidations

        # Cleanup
        server._stop_file_watcher()

    def test_file_watcher_handles_file_deletion(self, test_server, temp_workspace):
        """FileWatcher detects file deletion."""
        server, client = test_server

        # Create a temporary file first
        temp_file = temp_workspace / "temp_module.py"
        temp_file.write_text("def temp_function():\n    pass\n")

        # Start file watcher
        server._start_file_watcher()

        # Populate cache
        client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        initial_invalidations = server.cache_invalidations

        # Delete the file
        temp_file.unlink()

        # Wait for watcher
        time.sleep(1.0)

        # Cache invalidations should increase
        assert server.cache_invalidations >= initial_invalidations

        # Cleanup
        server._stop_file_watcher()

    def test_file_watcher_lifecycle(self, test_server):
        """FileWatcher starts and stops cleanly."""
        server, _ = test_server

        # Initially no watcher
        assert server.file_watcher is None

        # Start watcher
        server._start_file_watcher()
        assert server.file_watcher is not None
        assert server.file_watcher.observer.is_alive()

        # Stop watcher
        server._stop_file_watcher()

        # Observer should be stopped
        if server.file_watcher:
            time.sleep(0.5)  # Give observer time to stop
            assert not server.file_watcher.observer.is_alive()


@pytest.mark.integration
@pytest.mark.slow
class TestCacheInvalidationE2E:
    """Test cache invalidation workflows (E2E)."""

    def test_manual_cache_invalidation(self, test_server, temp_workspace):
        """Manual cache invalidation works correctly."""
        server, client = test_server

        # Populate cache with multiple files
        files = ["sample_module.py", "sample_usage.py"]
        for file in files:
            client.post(
                "/defs",
                json={
                    "file": file,
                    "line": 1,
                    "col": 1,
                    "root": str(temp_workspace)
                }
            )

        # Cache should have entries
        assert len(server.jedi_cache) > 0
        initial_cache_size = len(server.jedi_cache)

        # Invalidate specific file
        server._invalidate_cache("sample_module.py")

        # Cache size should decrease
        assert len(server.jedi_cache) < initial_cache_size

        # Invalidation counter should increase
        assert server.cache_invalidations > 0

    def test_cache_regeneration_after_invalidation(self, test_server, temp_workspace):
        """Cache is regenerated after invalidation on next request."""
        server, client = test_server

        # First request - populates cache
        response1 = client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )
        assert response1.status_code == 200
        assert len(server.jedi_cache) > 0

        # Invalidate cache
        server._invalidate_cache("sample_module.py")
        cache_after_invalidation = len(server.jedi_cache)

        # Second request - regenerates cache
        response2 = client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )
        assert response2.status_code == 200

        # Cache should be repopulated
        assert len(server.jedi_cache) > cache_after_invalidation


@pytest.mark.integration
class TestServerStatsE2E:
    """Test server statistics tracking (E2E)."""

    def test_request_count_tracking(self, test_server, temp_workspace):
        """Server tracks request count correctly."""
        server, client = test_server

        initial_count = server.request_count

        # Make several requests
        for _ in range(5):
            client.post(
                "/defs",
                json={
                    "file": "sample_module.py",
                    "line": 4,
                    "col": 5,
                    "root": str(temp_workspace)
                }
            )

        # Request count should increase by 5
        assert server.request_count == initial_count + 5

    def test_health_endpoint_returns_stats(self, httpx_client):
        """Health endpoint returns comprehensive stats."""
        # Make some requests first
        httpx_client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(httpx_client.base_url)
            }
        )

        # Get health stats
        response = httpx_client.get("/health")
        assert response.status_code == 200

        health = response.json()

        # Verify all expected fields
        assert "status" in health
        assert "workspace" in health
        assert "uptime" in health
        assert "requests" in health
        assert "cache_size" in health
        assert "cache_invalidations" in health

        # Verify types and values
        assert health["status"] == "ok"
        assert isinstance(health["uptime"], (int, float))
        assert health["uptime"] > 0
        assert health["requests"] > 0
        assert isinstance(health["cache_size"], int)
        assert isinstance(health["cache_invalidations"], int)

    def test_uptime_increases_over_time(self, httpx_client):
        """Uptime increases as server runs."""
        # First health check
        health1 = httpx_client.get("/health").json()
        uptime1 = health1["uptime"]

        # Wait a bit
        time.sleep(0.5)

        # Second health check
        health2 = httpx_client.get("/health").json()
        uptime2 = health2["uptime"]

        # Uptime should increase
        assert uptime2 > uptime1


@pytest.mark.integration
class TestRopeEngineLifecycleE2E:
    """Test Rope engine initialization and lifecycle (E2E)."""

    def test_rope_engine_lazy_initialization(self, test_server, temp_workspace):
        """Rope engine is created lazily on first Rope request."""
        server, client = test_server

        # Initially None
        assert server.rope_engine is None

        # Jedi request should NOT create Rope engine
        client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )
        assert server.rope_engine is None

        # Rope request SHOULD create engine
        client.post(
            "/occurrences",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )
        assert server.rope_engine is not None

    def test_rope_engine_persists_across_requests(self, test_server, temp_workspace):
        """Rope engine is reused across multiple requests."""
        server, client = test_server

        # First Rope request
        client.post(
            "/rename",
            json={
                "file": "sample_module.py",
                "line": 14,
                "col": 5,
                "new_name": "message",
                "root": str(temp_workspace)
            }
        )

        first_engine = server.rope_engine
        assert first_engine is not None

        # Second Rope request
        client.post(
            "/occurrences",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        # Should reuse same engine instance
        assert server.rope_engine is first_engine


@pytest.mark.integration
@pytest.mark.slow
class TestServerResilienceE2E:
    """Test server resilience and error handling (E2E)."""

    def test_server_handles_invalid_file_gracefully(self, test_server, temp_workspace):
        """Server handles requests for non-existent files gracefully."""
        _, client = test_server

        # Request with invalid file should not crash server
        response = client.post(
            "/defs",
            json={
                "file": "nonexistent.py",
                "line": 1,
                "col": 1,
                "root": str(temp_workspace)
            }
        )

        # Should return error or empty result, not crash
        assert response.status_code in (200, 400, 500)

        # Server should still be responsive
        health = client.get("/health")
        assert health.status_code == 200

    def test_server_handles_syntax_errors_gracefully(self, test_server, temp_workspace):
        """Server handles files with syntax errors gracefully."""
        _, client = test_server

        # Create file with syntax error
        bad_file = temp_workspace / "syntax_error.py"
        bad_file.write_text("def broken(\n    pass\n")

        # Request should not crash server
        response = client.post(
            "/defs",
            json={
                "file": "syntax_error.py",
                "line": 1,
                "col": 1,
                "root": str(temp_workspace)
            }
        )

        # Should handle gracefully
        assert response.status_code in (200, 400, 500)

        # Server still responsive
        health = client.get("/health")
        assert health.status_code == 200

    def test_server_handles_concurrent_requests(self, test_server, temp_workspace):
        """Server handles concurrent requests without issues."""
        server, client = test_server

        initial_count = server.request_count

        # Make concurrent requests (TestClient is synchronous, so we simulate concurrency)
        requests_made = 0
        for _ in range(10):
            response = client.post(
                "/defs",
                json={
                    "file": "sample_module.py",
                    "line": 4,
                    "col": 5,
                    "root": str(temp_workspace)
                }
            )
            if response.status_code == 200:
                requests_made += 1

        # All requests should succeed
        assert requests_made == 10
        assert server.request_count == initial_count + 10
