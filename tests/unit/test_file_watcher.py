"""Unit tests for FileWatcher."""

import time
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from pyclide_server.file_watcher import PythonFileWatcher


@pytest.mark.unit
class TestFileWatcher:
    """Test FileWatcher functionality."""

    def test_watcher_init(self, tmp_path):
        """FileWatcher initializes with workspace."""
        callback = Mock()
        watcher = PythonFileWatcher(tmp_path, callback)

        assert watcher.root == tmp_path
        assert watcher.on_change == callback
        assert watcher.observer is not None

    def test_watcher_detects_py_file_change(self, tmp_path):
        """Callback triggered on .py file modification."""
        callback = Mock()
        watcher = PythonFileWatcher(tmp_path, callback)

        # Create a Python file
        test_file = tmp_path / "test.py"
        test_file.write_text("# initial content\n")

        # Start watching
        watcher.start()
        time.sleep(0.2)  # Give watchdog time to start

        # Modify the file
        test_file.write_text("# modified content\n")

        # Wait for event to be processed
        time.sleep(0.5)

        # Stop watching
        watcher.stop()

        # Callback should have been called
        assert callback.call_count > 0

    def test_watcher_ignores_non_py_files(self, tmp_path):
        """No callback for non-Python files."""
        callback = Mock()
        watcher = PythonFileWatcher(tmp_path, callback)

        # Create a non-Python file
        test_file = tmp_path / "test.txt"
        test_file.write_text("initial content\n")

        # Start watching
        watcher.start()
        time.sleep(0.2)

        # Modify the file
        test_file.write_text("modified content\n")

        # Wait
        time.sleep(0.5)

        # Stop watching
        watcher.stop()

        # Callback should NOT have been called
        assert callback.call_count == 0

    def test_watcher_respects_hardcoded_ignores(self, tmp_path):
        """Ignores __pycache__, .venv, etc."""
        callback = Mock()
        watcher = PythonFileWatcher(tmp_path, callback)

        # Create __pycache__ directory with .py file
        pycache_dir = tmp_path / "__pycache__"
        pycache_dir.mkdir()
        test_file = pycache_dir / "test.py"
        test_file.write_text("# pycache file\n")

        # Start watching
        watcher.start()
        time.sleep(0.2)

        # Modify the file
        test_file.write_text("# modified\n")

        # Wait
        time.sleep(0.5)

        # Stop watching
        watcher.stop()

        # Callback should NOT have been called for __pycache__
        assert callback.call_count == 0

    def test_watcher_respects_gitignore(self, tmp_path):
        """Ignores files matching .gitignore patterns."""
        callback = Mock()

        # Create .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("ignored_*.py\n")

        watcher = PythonFileWatcher(tmp_path, callback)

        # Create ignored file
        test_file = tmp_path / "ignored_test.py"
        test_file.write_text("# ignored\n")

        # Start watching
        watcher.start()
        time.sleep(0.2)

        # Modify the file
        test_file.write_text("# modified\n")

        # Wait
        time.sleep(0.5)

        # Stop watching
        watcher.stop()

        # Callback should NOT have been called for gitignored file
        assert callback.call_count == 0

    def test_watcher_handles_file_creation(self, tmp_path):
        """Callback on new file creation."""
        callback = Mock()
        watcher = PythonFileWatcher(tmp_path, callback)

        # Start watching
        watcher.start()
        time.sleep(0.2)

        # Create a new Python file
        test_file = tmp_path / "new_file.py"
        test_file.write_text("# new file\n")

        # Wait for event
        time.sleep(0.5)

        # Stop watching
        watcher.stop()

        # Callback should have been called
        assert callback.call_count > 0

    def test_watcher_handles_file_deletion(self, tmp_path):
        """Callback on file deletion."""
        callback = Mock()
        watcher = PythonFileWatcher(tmp_path, callback)

        # Create a file before watching
        test_file = tmp_path / "to_delete.py"
        test_file.write_text("# will be deleted\n")

        # Start watching
        watcher.start()
        time.sleep(0.2)

        # Delete the file
        test_file.unlink()

        # Wait for event
        time.sleep(0.5)

        # Stop watching
        watcher.stop()

        # Callback should have been called
        assert callback.call_count > 0

    def test_watcher_stop(self, tmp_path):
        """Watcher stops cleanly."""
        callback = Mock()
        watcher = PythonFileWatcher(tmp_path, callback)

        # Start and immediately stop
        watcher.start()
        time.sleep(0.1)
        watcher.stop()

        # Should not raise exception
        assert True

    @pytest.mark.slow
    def test_watcher_debouncing(self, tmp_path):
        """Multiple rapid changes trigger callbacks (debouncing handled by callback)."""
        callback = Mock()
        watcher = PythonFileWatcher(tmp_path, callback)

        test_file = tmp_path / "debounce_test.py"
        test_file.write_text("# initial\n")

        # Start watching
        watcher.start()
        time.sleep(0.2)

        # Make multiple rapid changes
        for i in range(5):
            test_file.write_text(f"# change {i}\n")
            time.sleep(0.05)

        # Wait for events to be processed
        time.sleep(1.0)

        # Stop watching
        watcher.stop()

        # Should have been called multiple times (actual debouncing would be in callback logic)
        assert callback.call_count > 0
