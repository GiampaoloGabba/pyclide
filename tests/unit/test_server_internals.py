"""Comprehensive unit tests for PyCLIDEServer internal methods.

These tests cover private methods of pyclide_server/server.py:
- _get_rope_engine()
- _get_cached_script()
- _invalidate_cache()
- _update_activity()
- _start_file_watcher() / _stop_file_watcher()

NOTE: These are UNIT tests that test methods in isolation, unlike integration
tests that test via HTTP endpoints.
"""

import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from pyclide_server.server import PyCLIDEServer
from pyclide_server.rope_engine import RopeEngine


@pytest.mark.unit
class TestPyCLIDEServerInit:
    """Test PyCLIDEServer initialization."""

    def test_init_with_valid_workspace(self, tmp_path):
        """PyCLIDEServer initializes with valid workspace."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        assert server.root == tmp_path.resolve()
        assert server.port == 8888
        assert server.jedi_cache == {}
        assert server.rope_engine is None
        assert server.request_count == 0
        assert server.cache_invalidations == 0

    def test_init_creates_fastapi_app(self, tmp_path):
        """PyCLIDEServer creates FastAPI app."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        assert server.app is not None
        assert hasattr(server.app, 'routes')

    def test_init_resolves_workspace_path(self, tmp_path):
        """PyCLIDEServer resolves workspace root to absolute path."""
        # Use relative path
        relative = tmp_path / "subdir"
        relative.mkdir()

        server = PyCLIDEServer(str(relative), 8888)

        assert server.root.is_absolute()
        assert server.root == relative.resolve()

    def test_init_timestamps(self, tmp_path):
        """PyCLIDEServer initializes timestamps correctly."""
        before = time.time()
        server = PyCLIDEServer(str(tmp_path), 8888)
        after = time.time()

        assert before <= server.start_time <= after
        assert before <= server.last_activity <= after


@pytest.mark.unit
class TestGetRopeEngine:
    """Test PyCLIDEServer._get_rope_engine() method."""

    def test_get_rope_engine_lazy_init(self, tmp_path):
        """_get_rope_engine() creates RopeEngine on first call."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        # Initially None
        assert server.rope_engine is None

        # First call creates it
        engine = server._get_rope_engine()

        assert engine is not None
        assert isinstance(engine, RopeEngine)
        assert server.rope_engine is engine

    def test_get_rope_engine_reuse(self, tmp_path):
        """_get_rope_engine() reuses existing instance."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        # First call
        engine1 = server._get_rope_engine()

        # Second call should return same instance
        engine2 = server._get_rope_engine()

        assert engine1 is engine2

    def test_get_rope_engine_creates_project(self, tmp_path):
        """_get_rope_engine() creates Rope project for workspace."""
        # Create a simple Python file
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        server = PyCLIDEServer(str(tmp_path), 8888)
        engine = server._get_rope_engine()

        # Should have created Rope project
        assert engine.project is not None
        assert engine.root == tmp_path.resolve()


@pytest.mark.unit
class TestGetCachedScript:
    """Test PyCLIDEServer._get_cached_script() method."""

    def test_get_cached_script_cache_miss(self, tmp_path):
        """_get_cached_script() creates new Script on cache miss."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        server = PyCLIDEServer(str(tmp_path), 8888)

        # Cache should be empty
        assert len(server.jedi_cache) == 0

        # First call - cache miss
        script = server._get_cached_script("test.py")

        # Should have created and cached Script
        assert script is not None
        assert len(server.jedi_cache) == 1

    def test_get_cached_script_cache_hit(self, tmp_path):
        """_get_cached_script() returns cached Script on cache hit."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        server = PyCLIDEServer(str(tmp_path), 8888)

        # First call - populates cache
        script1 = server._get_cached_script("test.py")

        # Second call - should hit cache
        script2 = server._get_cached_script("test.py")

        # Same instance
        assert script1 is script2
        # Cache size unchanged
        assert len(server.jedi_cache) == 1

    def test_get_cached_script_multiple_files(self, tmp_path):
        """_get_cached_script() caches multiple files independently."""
        file1 = tmp_path / "file1.py"
        file1.write_text("x = 1\n")

        file2 = tmp_path / "file2.py"
        file2.write_text("y = 2\n")

        server = PyCLIDEServer(str(tmp_path), 8888)

        script1 = server._get_cached_script("file1.py")
        script2 = server._get_cached_script("file2.py")

        # Should have 2 cached scripts
        assert len(server.jedi_cache) == 2
        assert script1 is not script2

    def test_get_cached_script_uses_absolute_path(self, tmp_path):
        """_get_cached_script() uses absolute path as cache key."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        server = PyCLIDEServer(str(tmp_path), 8888)
        script = server._get_cached_script("test.py")

        # Cache key should be absolute path
        abs_path = str((tmp_path / "test.py").resolve())
        assert abs_path in server.jedi_cache

    def test_get_cached_script_nonexistent_file(self, tmp_path):
        """_get_cached_script() handles non-existent file."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        # Jedi raises FileNotFoundError for non-existent files
        with pytest.raises(FileNotFoundError):
            script = server._get_cached_script("nonexistent.py")

    def test_get_cached_script_nested_path(self, tmp_path):
        """_get_cached_script() handles nested directory structure."""
        subdir = tmp_path / "src" / "package"
        subdir.mkdir(parents=True)
        test_file = subdir / "module.py"
        test_file.write_text("x = 1\n")

        server = PyCLIDEServer(str(tmp_path), 8888)
        script = server._get_cached_script("src/package/module.py")

        assert script is not None
        assert len(server.jedi_cache) == 1


@pytest.mark.unit
class TestInvalidateCache:
    """Test PyCLIDEServer._invalidate_cache() method."""

    def test_invalidate_cache_removes_jedi_cache(self, tmp_path):
        """_invalidate_cache() removes file from Jedi cache."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        server = PyCLIDEServer(str(tmp_path), 8888)

        # Populate cache
        server._get_cached_script("test.py")
        assert len(server.jedi_cache) == 1

        # Invalidate
        server._invalidate_cache("test.py")

        # Cache should be empty
        assert len(server.jedi_cache) == 0

    def test_invalidate_cache_increments_counter(self, tmp_path):
        """_invalidate_cache() increments cache_invalidations counter."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        server = PyCLIDEServer(str(tmp_path), 8888)
        server._get_cached_script("test.py")

        initial_count = server.cache_invalidations

        server._invalidate_cache("test.py")

        assert server.cache_invalidations == initial_count + 1

    def test_invalidate_cache_non_cached_file(self, tmp_path):
        """_invalidate_cache() handles file not in cache (no-op)."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        # Cache is empty
        assert len(server.jedi_cache) == 0

        # Invalidate non-existent entry - should not crash
        server._invalidate_cache("nonexistent.py")

        # Counter still increments
        assert server.cache_invalidations == 1

    def test_invalidate_cache_calls_rope_validate(self, tmp_path):
        """_invalidate_cache() validates Rope project if engine exists."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        server = PyCLIDEServer(str(tmp_path), 8888)

        # Initialize Rope engine
        engine = server._get_rope_engine()

        # Mock the validate method
        with patch.object(engine.project, 'validate') as mock_validate:
            server._invalidate_cache("test.py")

            # Should have called validate
            mock_validate.assert_called_once()

    def test_invalidate_cache_without_rope_engine(self, tmp_path):
        """_invalidate_cache() works without Rope engine initialized."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        server = PyCLIDEServer(str(tmp_path), 8888)
        server._get_cached_script("test.py")

        # Rope engine is None
        assert server.rope_engine is None

        # Should not crash
        server._invalidate_cache("test.py")

        assert len(server.jedi_cache) == 0

    def test_invalidate_cache_multiple_times(self, tmp_path):
        """_invalidate_cache() can be called multiple times on same file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        server = PyCLIDEServer(str(tmp_path), 8888)
        server._get_cached_script("test.py")

        # Invalidate multiple times
        server._invalidate_cache("test.py")
        server._invalidate_cache("test.py")
        server._invalidate_cache("test.py")

        # Counter should increment each time
        assert server.cache_invalidations == 3


@pytest.mark.unit
class TestUpdateActivity:
    """Test PyCLIDEServer._update_activity() method."""

    def test_update_activity_increments_request_count(self, tmp_path):
        """_update_activity() increments request_count."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        initial_count = server.request_count

        server._update_activity()

        assert server.request_count == initial_count + 1

    def test_update_activity_updates_last_activity(self, tmp_path):
        """_update_activity() updates last_activity timestamp."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        old_activity = server.last_activity

        # Wait a bit
        time.sleep(0.01)

        server._update_activity()

        # Timestamp should be newer
        assert server.last_activity > old_activity

    def test_update_activity_multiple_calls(self, tmp_path):
        """_update_activity() can be called multiple times."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        for i in range(10):
            server._update_activity()

        assert server.request_count == 10

    def test_update_activity_timestamp_precision(self, tmp_path):
        """_update_activity() uses time.time() for timestamp."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        before = time.time()
        server._update_activity()
        after = time.time()

        # Timestamp should be between before and after
        assert before <= server.last_activity <= after


@pytest.mark.unit
class TestFileWatcherManagement:
    """Test PyCLIDEServer._start_file_watcher() and _stop_file_watcher()."""

    def test_start_file_watcher_creates_watcher(self, tmp_path):
        """_start_file_watcher() creates PythonFileWatcher."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        # Initially None
        assert server.file_watcher is None

        # Start watcher
        server._start_file_watcher()

        # Should have created watcher
        assert server.file_watcher is not None

    def test_start_file_watcher_with_callback(self, tmp_path):
        """_start_file_watcher() passes invalidate callback."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        with patch('pyclide_server.server.PythonFileWatcher') as MockWatcher:
            mock_instance = MagicMock()
            MockWatcher.return_value = mock_instance

            server._start_file_watcher()

            # Should have created watcher with root and callback
            MockWatcher.assert_called_once()
            call_args = MockWatcher.call_args
            assert call_args[0][0] == tmp_path.resolve()
            # Second arg should be the invalidate callback
            assert callable(call_args[0][1])

    def test_start_file_watcher_handles_failure(self, tmp_path):
        """_start_file_watcher() handles failure gracefully."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        with patch('pyclide_server.server.PythonFileWatcher', side_effect=Exception("Failed")):
            # Should not crash, just log warning
            server._start_file_watcher()

            # Watcher should be None
            assert server.file_watcher is None

    def test_stop_file_watcher_stops_watcher(self, tmp_path):
        """_stop_file_watcher() stops running watcher."""
        server = PyCLIDEServer(str(tmp_path), 8888)
        server._start_file_watcher()

        # Mock the watcher's stop method
        if server.file_watcher:
            with patch.object(server.file_watcher, 'stop') as mock_stop:
                server._stop_file_watcher()

                # Should have called stop
                mock_stop.assert_called_once()

    def test_stop_file_watcher_with_no_watcher(self, tmp_path):
        """_stop_file_watcher() handles None watcher (no-op)."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        # Watcher is None
        assert server.file_watcher is None

        # Should not crash
        server._stop_file_watcher()

    def test_stop_file_watcher_handles_error(self, tmp_path):
        """_stop_file_watcher() handles errors during stop."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        # Create mock watcher that raises on stop
        server.file_watcher = MagicMock()
        server.file_watcher.stop.side_effect = Exception("Stop failed")

        # Should not crash, just log error
        server._stop_file_watcher()


@pytest.mark.unit
class TestServerIntegration:
    """Integration tests for server internal methods working together."""

    def test_cache_lifecycle(self, tmp_path):
        """Test full cache lifecycle: create -> use -> invalidate."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def func():\n    pass\n")

        server = PyCLIDEServer(str(tmp_path), 8888)

        # 1. Create cache entry
        script1 = server._get_cached_script("test.py")
        assert len(server.jedi_cache) == 1

        # 2. Use cache (hit)
        script2 = server._get_cached_script("test.py")
        assert script1 is script2

        # 3. Invalidate
        server._invalidate_cache("test.py")
        assert len(server.jedi_cache) == 0

        # 4. Re-create (miss again)
        script3 = server._get_cached_script("test.py")
        assert len(server.jedi_cache) == 1
        # New Script instance
        assert script3 is not script1

    def test_activity_tracking(self, tmp_path):
        """Test activity tracking updates correctly."""
        server = PyCLIDEServer(str(tmp_path), 8888)

        initial_time = server.last_activity
        initial_count = server.request_count

        # Simulate multiple requests
        for i in range(5):
            server._update_activity()
            time.sleep(0.001)  # Small delay

        assert server.request_count == initial_count + 5
        assert server.last_activity > initial_time

    def test_rope_engine_and_cache_interaction(self, tmp_path):
        """Test Rope engine and Jedi cache work independently."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        server = PyCLIDEServer(str(tmp_path), 8888)

        # Create Jedi cache entry
        server._get_cached_script("test.py")
        assert len(server.jedi_cache) == 1

        # Create Rope engine
        engine = server._get_rope_engine()
        assert engine is not None

        # Invalidating cache should work with Rope initialized
        server._invalidate_cache("test.py")
        assert len(server.jedi_cache) == 0

        # Rope engine should still exist
        assert server.rope_engine is engine

    def test_multiple_file_cache(self, tmp_path):
        """Test caching multiple files and selective invalidation."""
        files = ["file1.py", "file2.py", "file3.py"]
        for filename in files:
            (tmp_path / filename).write_text("x = 1\n")

        server = PyCLIDEServer(str(tmp_path), 8888)

        # Cache all files
        for filename in files:
            server._get_cached_script(filename)

        assert len(server.jedi_cache) == 3

        # Invalidate only file2
        server._invalidate_cache("file2.py")

        assert len(server.jedi_cache) == 2
        # file1 and file3 should still be cached
        abs_file1 = str((tmp_path / "file1.py").resolve())
        abs_file3 = str((tmp_path / "file3.py").resolve())
        assert abs_file1 in server.jedi_cache
        assert abs_file3 in server.jedi_cache
