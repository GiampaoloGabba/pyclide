"""
File watcher for cache invalidation.
Monitors Python files and notifies server when changes occur.
"""

import logging
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable, Dict

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

try:
    import pathspec
    HAS_PATHSPEC = True
except ImportError:
    HAS_PATHSPEC = False

logger = logging.getLogger(__name__)


class PythonFileWatcher:
    """
    Monitor workspace for Python file changes.
    Notify server to invalidate cache on modifications.
    """

    def __init__(self, workspace_root: Path, on_change_callback: Callable[[str], None]):
        """
        Initialize file watcher.

        Args:
            workspace_root: Root directory to watch
            on_change_callback: Callback function called with relative file path on change
        """
        self.root = workspace_root
        self.on_change = on_change_callback
        self.observer = Observer()

        # Debouncing: avoid multiple notifications for same modification
        self.last_modified: Dict[str, float] = {}
        self.debounce_seconds = 0.1

        # Ignore patterns (hardcoded + .gitignore)
        self._setup_ignore_patterns()

        logger.info(f"File watcher initialized for {workspace_root}")

    def _setup_ignore_patterns(self):
        """Setup ignore patterns from hardcoded list + .gitignore."""
        # Hardcoded patterns (common Python artifacts)
        self.hardcoded_ignore = [
            '**/__pycache__/**',
            '**/.venv/**',
            '**/venv/**',
            '**/env/**',
            '**/.git/**',
            '**/*.pyc',
            '**/*.pyo',
            '**/*.pyd',
            '**/.swp',
            '**/*.tmp',
            '**/node_modules/**',
            '**/.pytest_cache/**',
            '**/.mypy_cache/**',
            '**/.ruff_cache/**',
            '**/.ropeproject/**',
            '**/.pyclide/**',
            '**/build/**',
            '**/dist/**',
            '**/*.egg-info/**',
        ]

        # Load .gitignore if exists
        self.gitignore_spec = None
        gitignore_path = self.root / ".gitignore"
        if gitignore_path.exists() and HAS_PATHSPEC:
            try:
                with open(gitignore_path, 'r') as f:
                    patterns = f.readlines()
                self.gitignore_spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)
                logger.info("Loaded .gitignore patterns")
            except Exception as e:
                logger.warning(f"Failed to load .gitignore: {e}")

    def _should_ignore(self, path: str) -> bool:
        """
        Check if path should be ignored.

        Args:
            path: Absolute path to check

        Returns:
            True if path should be ignored
        """
        # Check hardcoded patterns
        for pattern in self.hardcoded_ignore:
            if fnmatch(path, pattern):
                return True

        # Check .gitignore patterns
        if self.gitignore_spec:
            try:
                rel_path = Path(path).relative_to(self.root)
                if self.gitignore_spec.match_file(str(rel_path)):
                    return True
            except Exception:
                pass

        return False

    def start(self):
        """Start monitoring filesystem."""
        handler = PythonFileHandler(self._on_file_event)
        self.observer.schedule(handler, str(self.root), recursive=True)
        self.observer.start()
        logger.info("File watcher started")

    def stop(self):
        """Stop monitoring."""
        self.observer.stop()
        self.observer.join()
        logger.info("File watcher stopped")

    def _on_file_event(self, event: FileSystemEvent):
        """
        Handle file modification event.

        Args:
            event: Filesystem event from watchdog
        """
        # Ignore directory events
        if event.is_directory:
            return

        # Only watch .py files
        if not event.src_path.endswith('.py'):
            return

        # Check ignore patterns
        if self._should_ignore(event.src_path):
            return

        # Debouncing: avoid multiple calls for same file in short time
        now = time.time()
        if event.src_path in self.last_modified:
            if now - self.last_modified[event.src_path] < self.debounce_seconds:
                return

        self.last_modified[event.src_path] = now

        # Notify server (convert to relative path)
        try:
            rel_path = Path(event.src_path).relative_to(self.root)
            logger.debug(f"File changed: {rel_path}")
            self.on_change(str(rel_path))
        except Exception as e:
            logger.error(f"Error processing file event: {e}")


class PythonFileHandler(FileSystemEventHandler):
    """Handler for filesystem events."""

    def __init__(self, callback: Callable[[FileSystemEvent], None]):
        """
        Initialize handler.

        Args:
            callback: Function to call on file events
        """
        self.callback = callback

    def on_modified(self, event):
        """Called when file is modified."""
        self.callback(event)

    def on_created(self, event):
        """Called when file is created."""
        self.callback(event)

    def on_deleted(self, event):
        """Called when file is deleted."""
        self.callback(event)

    def on_moved(self, event):
        """Called when file is moved."""
        self.callback(event)
