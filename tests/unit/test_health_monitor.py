"""Unit tests for HealthMonitor."""

import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch

import pytest

from pyclide_server.health import HealthMonitor


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.skip(reason="pytest-asyncio not installed - async tests require pytest-asyncio")
class TestHealthMonitor:
    """Test HealthMonitor functionality."""

    def test_monitor_init(self):
        """HealthMonitor initializes with server."""
        mock_server = Mock()
        mock_server.last_activity = time.time()
        mock_server.start_time = time.time()
        mock_server.request_count = 0
        mock_server.root = "/workspace"

        monitor = HealthMonitor(mock_server)

        assert monitor.server == mock_server
        assert monitor.running is False

    async def test_monitor_inactivity_timeout(self):
        """Shutdown triggered after inactivity threshold."""
        mock_server = Mock()
        mock_server.last_activity = time.time() - 7200  # 2 hours ago
        mock_server.start_time = time.time()
        mock_server.request_count = 0
        mock_server.root = "/workspace"

        monitor = HealthMonitor(mock_server, inactivity_timeout=3600)  # 1 hour
        monitor._graceful_shutdown = AsyncMock()

        # Check if inactivity is detected
        inactive_time = time.time() - mock_server.last_activity
        assert inactive_time > monitor.inactivity_timeout

        # Simulate one check iteration
        await monitor._health_check()

        # Should trigger shutdown
        monitor._graceful_shutdown.assert_called_once()

    async def test_monitor_memory_warning(self):
        """Warning logged at memory threshold (if psutil available)."""
        mock_server = Mock()
        mock_server.last_activity = time.time()
        mock_server.start_time = time.time()
        mock_server.request_count = 0
        mock_server.root = "/workspace"

        monitor = HealthMonitor(mock_server, memory_warning_mb=1)  # Very low threshold

        with patch('pyclide_server.health.logger') as mock_logger:
            try:
                import psutil
                # Run health check
                await monitor._health_check()

                # Should log memory stats (warning or info)
                assert mock_logger.info.called or mock_logger.warning.called
            except ImportError:
                # psutil not available, skip
                pytest.skip("psutil not installed")

    async def test_monitor_memory_limit_shutdown(self):
        """Shutdown triggered at memory limit."""
        mock_server = Mock()
        mock_server.last_activity = time.time()
        mock_server.start_time = time.time()
        mock_server.request_count = 0
        mock_server.root = "/workspace"

        # Set unrealistically low memory limit to trigger shutdown
        monitor = HealthMonitor(mock_server, memory_limit_mb=1)
        monitor._graceful_shutdown = AsyncMock()

        try:
            import psutil
            # Run health check
            await monitor._health_check()

            # Should trigger shutdown due to memory limit
            monitor._graceful_shutdown.assert_called_once()
        except ImportError:
            pytest.skip("psutil not installed")

    async def test_monitor_health_check_updates_stats(self):
        """Health check logs server stats."""
        mock_server = Mock()
        mock_server.last_activity = time.time()
        mock_server.start_time = time.time() - 100  # Running for 100 seconds
        mock_server.request_count = 42
        mock_server.root = "/workspace"

        monitor = HealthMonitor(mock_server)

        with patch('pyclide_server.health.logger') as mock_logger:
            await monitor._health_check()

            # Should log stats
            assert mock_logger.info.called
            # Check that stats were included in log
            call_args = str(mock_logger.info.call_args)
            assert "42" in call_args  # request count

    async def test_monitor_stop(self):
        """Monitor stops gracefully."""
        mock_server = Mock()
        mock_server.last_activity = time.time()
        mock_server.start_time = time.time()
        mock_server.request_count = 0
        mock_server.root = "/workspace"

        monitor = HealthMonitor(mock_server)
        monitor.running = True

        monitor.stop()

        assert monitor.running is False

    async def test_monitor_start_stop_cycle(self):
        """Monitor can start and stop properly."""
        mock_server = Mock()
        mock_server.last_activity = time.time()
        mock_server.start_time = time.time()
        mock_server.request_count = 0
        mock_server.root = "/workspace"

        monitor = HealthMonitor(mock_server, check_interval=0.1)

        # Start monitoring in background
        task = asyncio.create_task(monitor.start())

        # Wait a bit
        await asyncio.sleep(0.2)

        # Stop monitoring
        monitor.stop()

        # Wait for task to complete
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.TimeoutError:
            pytest.fail("Monitor did not stop within timeout")

    async def test_monitor_no_shutdown_when_active(self):
        """No shutdown when server is active."""
        mock_server = Mock()
        mock_server.last_activity = time.time()  # Just now
        mock_server.start_time = time.time()
        mock_server.request_count = 100
        mock_server.root = "/workspace"

        monitor = HealthMonitor(mock_server, inactivity_timeout=3600)
        monitor._graceful_shutdown = AsyncMock()

        await monitor._health_check()

        # Should NOT trigger shutdown
        monitor._graceful_shutdown.assert_not_called()
