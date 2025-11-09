"""Integration tests for cache invalidation."""

import time

import pytest

from tests.utils import create_python_file


@pytest.mark.integration
class TestCacheInvalidation:
    """Test cache invalidation with file watcher integration."""

    def test_cache_stats_updated(self, test_server, temp_workspace):
        """Request updates cache statistics."""
        server, client = test_server

        # Initial state
        health1 = client.get("/health").json()
        initial_cache_size = health1["cache_size"]
        initial_invalidations = health1.get("cache_invalidations", 0)

        # Make a request to populate cache
        client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        # Cache should have grown
        health2 = client.get("/health").json()
        assert health2["cache_size"] > initial_cache_size

    def test_jedi_cache_grows_with_files(self, httpx_client, temp_workspace):
        """Jedi cache grows as different files are accessed."""
        # Initial cache size
        health1 = httpx_client.get("/health").json()
        initial_size = health1["cache_size"]

        # Access first file
        httpx_client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        health2 = httpx_client.get("/health").json()
        size_after_first = health2["cache_size"]
        assert size_after_first >= initial_size

        # Access second file
        httpx_client.post(
            "/defs",
            json={
                "file": "sample_usage.py",
                "line": 6,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        health3 = httpx_client.get("/health").json()
        size_after_second = health3["cache_size"]
        assert size_after_second >= size_after_first

    def test_rope_lazy_initialization(self, test_server, temp_workspace):
        """Rope not loaded until first refactoring request."""
        server, client = test_server

        # Initially, rope_engine should be None
        assert server.rope_engine is None

        # Make a Jedi request (shouldn't load Rope)
        client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        # Rope still not loaded
        assert server.rope_engine is None

        # Make a Rope request
        client.post(
            "/occurrences",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        # Now Rope should be loaded
        assert server.rope_engine is not None

    @pytest.mark.slow
    def test_cache_invalidated_on_file_change(self, test_server, temp_workspace):
        """Jedi cache cleared when monitored file changes."""
        server, client = test_server

        # Start file watcher
        server._start_file_watcher()
        time.sleep(0.2)  # Let watcher start

        try:
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

            initial_invalidations = client.get("/health").json().get("cache_invalidations", 0)

            # Modify the file
            test_file = temp_workspace / "sample_module.py"
            original_content = test_file.read_text()
            test_file.write_text(original_content + "\n# Modified\n")

            # Wait for file watcher to detect change
            time.sleep(1.0)

            # Check invalidations increased
            new_invalidations = client.get("/health").json().get("cache_invalidations", 0)
            assert new_invalidations > initial_invalidations

        finally:
            server._stop_file_watcher()

    @pytest.mark.slow
    def test_rope_validated_on_file_change(self, test_server, temp_workspace):
        """Rope project validated after file change."""
        server, client = test_server

        # Start file watcher
        server._start_file_watcher()
        time.sleep(0.2)

        try:
            # Load Rope by making a refactoring request
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
            initial_invalidations = client.get("/health").json().get("cache_invalidations", 0)

            # Modify a file
            test_file = temp_workspace / "sample_module.py"
            original_content = test_file.read_text()
            test_file.write_text(original_content + "\n# Modified for Rope test\n")

            # Wait for file watcher
            time.sleep(1.0)

            # Invalidations should have increased
            new_invalidations = client.get("/health").json().get("cache_invalidations", 0)
            assert new_invalidations > initial_invalidations

        finally:
            server._stop_file_watcher()

    @pytest.mark.slow
    def test_ignored_file_no_invalidation(self, test_server, temp_workspace):
        """Cache not invalidated for .gitignored files."""
        server, client = test_server

        # Create .gitignore
        gitignore = temp_workspace / ".gitignore"
        gitignore.write_text("ignored_*.py\n")

        # Start file watcher
        server._start_file_watcher()
        time.sleep(0.2)

        try:
            initial_invalidations = client.get("/health").json().get("cache_invalidations", 0)

            # Create and modify an ignored file
            ignored_file = temp_workspace / "ignored_test.py"
            create_python_file(ignored_file, "# This is ignored\n")

            time.sleep(0.5)

            # Modify it
            ignored_file.write_text("# Modified ignored file\n")

            time.sleep(1.0)

            # Invalidations should NOT increase
            new_invalidations = client.get("/health").json().get("cache_invalidations", 0)
            assert new_invalidations == initial_invalidations

        finally:
            server._stop_file_watcher()
