"""
Health monitoring and auto-shutdown for server lifecycle management.
"""

import asyncio
import logging
import os
import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .server import PyCLIDEServer

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Monitor server health and trigger auto-shutdown when needed.

    Monitors:
    - Inactivity timeout (default: 30 minutes)
    - Memory usage (warning threshold)
    - Error tracking
    """

    def __init__(self, server: 'PyCLIDEServer'):
        """
        Initialize health monitor.

        Args:
            server: PyCLIDEServer instance to monitor
        """
        self.server = server
        self.check_interval = 30  # seconds between health checks
        self.inactivity_timeout = 1800  # 30 minutes in seconds
        self.memory_warning_mb = 500  # Log warning at 500MB
        self.memory_limit_mb = 1000  # Force shutdown at 1GB

        self.running = False
        self.task: asyncio.Task = None

    async def start(self):
        """Start health monitoring loop."""
        self.running = True
        logger.info("Health monitor started")

        while self.running:
            try:
                await asyncio.sleep(self.check_interval)
                await self._health_check()
            except Exception as e:
                logger.error(f"Health check error: {e}", exc_info=True)

    def stop(self):
        """Stop health monitoring."""
        self.running = False
        logger.info("Health monitor stopped")

    async def _health_check(self):
        """Perform health checks."""
        # Check inactivity timeout
        inactive_seconds = time.time() - self.server.last_activity
        if inactive_seconds > self.inactivity_timeout:
            logger.info(
                f"Server inactive for {inactive_seconds:.0f}s "
                f"(threshold: {self.inactivity_timeout}s). Shutting down..."
            )
            await self._graceful_shutdown()
            return

        # Check memory usage (if psutil available)
        if HAS_PSUTIL:
            try:
                process = psutil.Process(os.getpid())
                memory_mb = process.memory_info().rss / 1024 / 1024

                if memory_mb > self.memory_limit_mb:
                    logger.warning(
                        f"Memory usage {memory_mb:.1f}MB exceeds limit {self.memory_limit_mb}MB. "
                        "Shutting down..."
                    )
                    await self._graceful_shutdown()
                    return
                elif memory_mb > self.memory_warning_mb:
                    logger.warning(
                        f"High memory usage: {memory_mb:.1f}MB "
                        f"(cache size: {len(self.server.jedi_cache)} files)"
                    )
            except Exception as e:
                logger.debug(f"Memory check failed: {e}")

        # Log stats
        logger.debug(
            f"Health check OK - "
            f"uptime: {time.time() - self.server.start_time:.0f}s, "
            f"requests: {self.server.request_count}, "
            f"cache size: {len(self.server.jedi_cache)}, "
            f"invalidations: {self.server.cache_invalidations}"
        )

    async def _graceful_shutdown(self):
        """Shutdown server gracefully."""
        logger.info("Initiating graceful shutdown...")

        # Stop file watcher
        self.server._stop_file_watcher()

        # Close Rope project
        if self.server.rope_engine:
            try:
                self.server.rope_engine.project.close()
            except Exception as e:
                logger.error(f"Error closing Rope project: {e}")

        # Stop health monitor
        self.stop()

        # Exit process
        logger.info("Server shutdown complete")
        sys.exit(0)
