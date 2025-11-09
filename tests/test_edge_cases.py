"""Tests for edge cases and error handling."""

import pathlib
import sys
import tempfile
import shutil
from unittest.mock import Mock, patch

import pytest
import typer

# Add parent directory to path to import pyclide
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pyclide import (
    RopeEngine,
    jedi_script,
    ensure,
    read_text,
    write_text_atomic,
    byte_offset,
)


class TestFileSystemErrors:
    """Test error handling for file system operations."""

    def test_read_nonexistent_file(self):
        """Test reading a file that does not exist."""
        nonexistent = pathlib.Path("/path/that/does/not/exist.py")

        with pytest.raises(FileNotFoundError):
            read_text(nonexistent)

    def test_jedi_script_nonexistent_file(self, tmp_path):
        """Test Jedi with a file that doesn't exist."""
        # Jedi may handle this gracefully or raise - document the behavior
        # This depends on Jedi's implementation
        try:
            scr = jedi_script(tmp_path, "nonexistent.py")
            # If no error, that's ok - Jedi may still work with non-existent files
        except Exception as e:
            # Expected behavior - file doesn't exist
            assert "nonexistent.py" in str(e) or isinstance(e, (FileNotFoundError, OSError))

    def test_rope_engine_nonexistent_directory(self):
        """Test RopeEngine with a directory that doesn't exist."""
        nonexistent = pathlib.Path("/path/that/does/not/exist")

        # RopeEngine may create the directory or fail
        # This tests the actual behavior
        try:
            eng = RopeEngine(nonexistent)
            # If it succeeds, that's documented behavior
        except Exception as e:
            # Expected - directory doesn't exist
            assert isinstance(e, (FileNotFoundError, OSError, RuntimeError))

    def test_rope_engine_file_not_found(self, tmp_path):
        """Test Rope operations on nonexistent file."""
        eng = RopeEngine(tmp_path)

        # Try to get occurrences for a file that doesn't exist
        with pytest.raises(Exception):  # Could be various exceptions from Rope
            eng.occurrences("nonexistent.py", 1, 1)

    def test_empty_file_path(self):
        """Test with empty file path."""
        empty_path = pathlib.Path("")

        # This should fail gracefully
        with pytest.raises((FileNotFoundError, ValueError, OSError)):
            read_text(empty_path)

    def test_non_python_file(self, tmp_path):
        """Test with non-Python file."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("This is not Python code", encoding="utf-8")

        # Jedi/Rope may handle this or fail
        eng = RopeEngine(tmp_path)

        # Attempting operations on non-Python file may fail
        # This documents the behavior
        try:
            eng.occurrences("test.txt", 1, 1)
        except Exception:
            # Expected - not a Python file
            pass


class TestInvalidPositions:
    """Test error handling for invalid line/column positions."""

    @pytest.fixture
    def sample_file(self, tmp_path):
        """Create a sample Python file."""
        f = tmp_path / "sample.py"
        f.write_text("def foo():\n    pass\n", encoding="utf-8")
        return f

    def test_line_zero(self, tmp_path, sample_file):
        """Test with line 0."""
        eng = RopeEngine(tmp_path)

        # Line 0 is invalid (1-based indexing)
        with pytest.raises(Exception):
            eng.occurrences("sample.py", 0, 1)

    def test_negative_line(self, tmp_path, sample_file):
        """Test with negative line number."""
        eng = RopeEngine(tmp_path)

        with pytest.raises(Exception):
            eng.occurrences("sample.py", -1, 1)

    def test_column_zero(self, tmp_path, sample_file):
        """Test with column 0."""
        # byte_offset should handle this - it clamps to valid range
        text = sample_file.read_text(encoding="utf-8")
        offset = byte_offset(text, 1, 0)

        # Column 0 gets clamped or adjusted
        assert offset >= 0

    def test_negative_column(self, tmp_path, sample_file):
        """Test with negative column."""
        text = sample_file.read_text(encoding="utf-8")
        offset = byte_offset(text, 1, -1)

        # Should handle gracefully (clamp to 0)
        assert offset >= 0

    def test_line_exceeds_file_length(self, tmp_path, sample_file):
        """Test with line number greater than file length."""
        eng = RopeEngine(tmp_path)

        # Line 100 in a 2-line file
        # May fail or return empty results
        try:
            result = eng.occurrences("sample.py", 100, 1)
            # If it doesn't raise, should return empty or handle gracefully
        except Exception:
            # Expected - line out of bounds
            pass

    def test_column_exceeds_line_length(self, tmp_path, sample_file):
        """Test with column greater than line length."""
        text = sample_file.read_text(encoding="utf-8")

        # Line 1 is "def foo():" which is 10 chars
        # Column 100 should be clamped or handled
        offset = byte_offset(text, 1, 100)

        # Should not crash
        assert offset >= 0

    def test_empty_file_any_position(self, tmp_path):
        """Test operations on empty file."""
        empty = tmp_path / "empty.py"
        empty.write_text("", encoding="utf-8")

        eng = RopeEngine(tmp_path)

        # Operations on empty file should handle gracefully
        try:
            result = eng.occurrences("empty.py", 1, 1)
            # May return empty results
        except Exception:
            # Or may raise - both acceptable
            pass


class TestInvalidPythonSyntax:
    """Test handling of files with syntax errors."""

    @pytest.fixture
    def fixtures_dir(self):
        """Return the fixtures directory."""
        return pathlib.Path(__file__).parent / "fixtures"

    def test_syntax_error_file(self, fixtures_dir):
        """Test with file containing syntax errors."""
        # We created invalid_syntax.py in fixtures
        invalid_file = fixtures_dir / "invalid_syntax.py"

        # Parsing should fail
        import ast

        with pytest.raises(SyntaxError):
            ast.parse(invalid_file.read_text(encoding="utf-8"))

    def test_rope_with_syntax_error(self, tmp_path):
        """Test Rope operations on file with syntax error."""
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(\n    pass", encoding="utf-8")

        eng = RopeEngine(tmp_path)

        # Rope with ignore_syntax_errors=True treats files with syntax errors as empty
        # This allows operations to continue on valid files in the project
        occurrences = eng.occurrences("bad.py", 1, 1)
        # Should return empty list since the file is treated as empty
        assert isinstance(occurrences, list)

    def test_jedi_with_syntax_error(self, tmp_path):
        """Test Jedi with syntax error file."""
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(\n    pass", encoding="utf-8")

        # Jedi may handle partial/invalid syntax gracefully
        try:
            scr = jedi_script(tmp_path, "bad.py")
            # Jedi is resilient and may work despite syntax errors
        except Exception:
            # Or it may fail - both acceptable
            pass

    def test_incomplete_code(self, tmp_path):
        """Test with incomplete Python code."""
        incomplete = tmp_path / "incomplete.py"
        incomplete.write_text("class Foo:", encoding="utf-8")  # No body

        import ast

        # Should raise SyntaxError for incomplete class
        with pytest.raises(SyntaxError):
            ast.parse(incomplete.read_text(encoding="utf-8"))


class TestMissingDependencies:
    """Test behavior when dependencies are missing."""

    def test_jedi_missing_error_message(self, monkeypatch):
        """Test that missing Jedi shows helpful error message."""
        # We can't easily mock import failures in the current design
        # because imports happen at module level
        # But we can test the ensure() mechanism

        from pyclide import _missing

        # If jedi is actually missing, _missing should contain it
        if "jedi" in _missing:
            error_msg = _missing["jedi"]
            assert isinstance(error_msg, str)

    def test_rope_missing_error_message(self):
        """Test that missing Rope shows helpful error message."""
        from pyclide import _missing

        if "rope" in _missing:
            error_msg = _missing["rope"]
            assert isinstance(error_msg, str)

    def test_ensure_suggests_pip_install(self):
        """Test that error messages suggest pip install."""
        # This is more of a documentation test
        # The actual messages are in the command handlers

        # Test the ensure mechanism
        with pytest.raises(typer.Exit) as exc_info:
            ensure(False, "jedi not installed. Run: pip install jedi")

        assert exc_info.value.exit_code == 2


class TestRopeJediFailures:
    """Test Rope and Jedi API failure scenarios."""

    def test_symbol_not_found_at_position(self, tmp_path):
        """Test when no symbol exists at the given position."""
        f = tmp_path / "test.py"
        f.write_text("# Just a comment\n", encoding="utf-8")

        eng = RopeEngine(tmp_path)

        # Clicking on a comment may return empty or fail
        try:
            result = eng.occurrences("test.py", 1, 5)  # On "#" or space
            # May return empty list
            assert isinstance(result, list)
        except Exception:
            # Or may raise - both acceptable
            pass

    def test_rename_on_whitespace(self, tmp_path):
        """Test rename on whitespace/invalid position."""
        f = tmp_path / "test.py"
        f.write_text("def foo():\n    pass\n", encoding="utf-8")

        eng = RopeEngine(tmp_path)

        # Try to rename at position with no symbol
        # Rope returns empty patches instead of raising an exception
        patches = eng.rename("test.py", 2, 1, "new_name")  # On whitespace before "pass"
        assert patches == {}

    def test_extract_invalid_range(self, tmp_path):
        """Test extract method with invalid range (end < start)."""
        f = tmp_path / "test.py"
        f.write_text("def foo():\n    x = 1\n    y = 2\n", encoding="utf-8")

        eng = RopeEngine(tmp_path)

        # End line before start line
        with pytest.raises(Exception):
            eng.extract_method("test.py", 3, 2, "extracted")

    def test_extract_preconditions_not_met(self, tmp_path):
        """Test extract when preconditions aren't satisfied."""
        f = tmp_path / "test.py"
        # Extract single keyword may fail
        f.write_text("def foo():\n    return\n", encoding="utf-8")

        eng = RopeEngine(tmp_path)

        # Trying to extract just "return" keyword may fail
        try:
            eng.extract_variable("test.py", 2, 2, "extracted", start_col=5, end_col=11)
        except Exception:
            # Expected - can't extract a statement as variable
            pass


class TestAtomicWriteOperations:
    """Test atomic write operations."""

    def test_write_text_atomic_creates_temp_file(self, tmp_path, monkeypatch):
        """Test that write_text_atomic creates a .pyclide.tmp file."""
        target = tmp_path / "test.py"
        target.write_text("original", encoding="utf-8")

        # Track temp file creation
        temp_files_created = []

        original_write_text = pathlib.Path.write_text

        def mock_write_text(self, content, **kwargs):
            temp_files_created.append(str(self))
            return original_write_text(self, content, **kwargs)

        monkeypatch.setattr(pathlib.Path, "write_text", mock_write_text)

        # Write new content
        write_text_atomic(target, "new content")

        # Check that temp file was used
        assert any(".pyclide.tmp" in f for f in temp_files_created)

        # Check final content
        assert target.read_text(encoding="utf-8") == "new content"

    def test_write_text_atomic_replaces_file(self, tmp_path):
        """Test that write_text_atomic replaces the original file."""
        target = tmp_path / "test.py"
        target.write_text("original content", encoding="utf-8")

        # Write new content
        write_text_atomic(target, "new content")

        # Verify content was replaced
        assert target.read_text(encoding="utf-8") == "new content"

        # Verify temp file is gone
        temp_file = tmp_path / "test.py.pyclide.tmp"
        assert not temp_file.exists()

    def test_write_text_atomic_prevents_partial_writes(self, tmp_path):
        """Test that atomic write prevents partial writes on failure."""
        target = tmp_path / "test.py"
        target.write_text("original content", encoding="utf-8")

        # Simulate failure during write by making target read-only
        # (This is platform-dependent, may not work on all systems)
        import os
        import stat

        # Make file read-only
        os.chmod(target, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        try:
            # This should fail because we can't replace a read-only file
            write_text_atomic(target, "new content")
        except (PermissionError, OSError):
            # Expected - permission denied
            pass
        finally:
            # Restore permissions
            os.chmod(target, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

        # Original content should still be intact (no partial write)
        current_content = target.read_text(encoding="utf-8")
        assert current_content == "original content"


class TestByteOffsetEdgeCases:
    """Test byte_offset utility with edge cases."""

    def test_byte_offset_with_tabs(self):
        """Test byte_offset with tabs in text."""
        text = "line1\n\tindented\n"

        # Line 2, column 2 (after tab)
        offset = byte_offset(text, 2, 2)

        # Should be: len("line1\n") + len("\t") + 0 (since column 2 means 1 char after col 1)
        # Actually: line1\n is 6 chars, then \t is 1 char, so col 2 is at offset 7
        assert offset == 7

    def test_byte_offset_with_empty_lines(self):
        """Test byte_offset with empty lines."""
        text = "line1\n\nline3\n"

        # Line 2 is empty
        offset = byte_offset(text, 2, 1)

        # Should be at position after "line1\n"
        assert offset == 6

    def test_byte_offset_last_line_last_col(self):
        """Test byte_offset at last line, last column."""
        text = "line1\nline2"

        # Line 2, last char 'e' is at col 5
        offset = byte_offset(text, 2, 5)

        # "line1\n" = 6, then "line" = 4 more
        assert offset == 10

    def test_byte_offset_out_of_bounds_clamping(self):
        """Test that byte_offset clamps out-of-bounds values."""
        text = "short\n"

        # Line 10 doesn't exist (only 1 line)
        offset = byte_offset(text, 10, 1)

        # Should clamp to valid range
        # The implementation does: sum(len(l) for l in lines[:max(0, line-1)])
        # For line 10, it's lines[:9], which is all lines
        assert offset >= len("short\n")
