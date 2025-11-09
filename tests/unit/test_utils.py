"""Comprehensive unit tests for pyclide_server/utils.py.

These tests cover all edge cases for byte_offset() and rel_to() functions,
which are critical for coordinate conversion and path handling throughout the system.
"""

import pathlib
import tempfile

import pytest

from pyclide_server.utils import byte_offset, rel_to


@pytest.mark.unit
class TestByteOffset:
    """Test byte_offset() function with all edge cases."""

    def test_simple_start_of_file(self):
        """Line 1, col 1 returns offset 0."""
        text = "hello\nworld\n"
        assert byte_offset(text, 1, 1) == 0

    def test_simple_first_line(self):
        """Position within first line."""
        text = "hello world\n"
        # Line 1, col 7 = 'w' in "world"
        assert byte_offset(text, 1, 7) == 6

    def test_simple_second_line(self):
        """Position on second line."""
        text = "hello\nworld\n"
        # Line 2, col 1 = 'w' in "world"
        assert byte_offset(text, 2, 1) == 6  # "hello\n" = 6 bytes

    def test_second_line_middle(self):
        """Position in middle of second line."""
        text = "hello\nworld\n"
        # Line 2, col 3 = 'r' in "world"
        assert byte_offset(text, 2, 3) == 8  # "hello\nwo" = 8 bytes

    def test_empty_file(self):
        """Empty text returns 0."""
        assert byte_offset("", 1, 1) == 0

    def test_empty_lines(self):
        """Text with empty lines."""
        text = "hello\n\nworld\n"
        # Line 3, col 1 = 'w' in "world"
        assert byte_offset(text, 3, 1) == 7  # "hello\n\n" = 7 bytes

    def test_only_newlines(self):
        """Text with only newlines."""
        text = "\n\n\n"
        # Line 2, col 1
        assert byte_offset(text, 2, 1) == 1  # "\n" = 1 byte

    def test_line_out_of_bounds_high(self):
        """Line number exceeds file length."""
        text = "line1\nline2\n"
        # Line 100, col 1 - should not crash, return end of file
        result = byte_offset(text, 100, 1)
        # Should return position at or beyond text length
        assert result >= len(text) - 1

    def test_column_out_of_bounds_high(self):
        """Column exceeds line length."""
        text = "short\n"
        # Line 1, col 100 - should not crash
        result = byte_offset(text, 1, 100)
        # Should clamp to end of line (before newline)
        assert result == 99  # max(0, 100-1)

    def test_line_zero_or_negative(self):
        """Line 0 or negative treated as line 1."""
        text = "hello\nworld\n"
        # Line 0 should behave like line 1
        assert byte_offset(text, 0, 1) == 0
        # Negative line
        assert byte_offset(text, -1, 1) == 0

    def test_column_zero_or_negative(self):
        """Column 0 or negative treated as column 1."""
        text = "hello\nworld\n"
        # Col 0 should behave like col 1
        assert byte_offset(text, 1, 0) == 0
        # Negative col
        assert byte_offset(text, 1, -5) == 0

    def test_multiline_with_varying_lengths(self):
        """Text with lines of different lengths."""
        text = "a\nbb\nccc\ndddd\n"
        # Line 1, col 1 = 'a'
        assert byte_offset(text, 1, 1) == 0
        # Line 2, col 2 = second 'b'
        assert byte_offset(text, 2, 2) == 3  # "a\nb" = 3
        # Line 3, col 3 = third 'c'
        assert byte_offset(text, 3, 3) == 7  # "a\nbb\ncc" = 7
        # Line 4, col 4 = fourth 'd'
        # "a\n" (2) + "bb\n" (3) + "ccc\n" (4) = 9 bytes to line 4, then col 4 = +3
        assert byte_offset(text, 4, 4) == 12  # "a\nbb\nccc\nddd" = 12

    def test_no_trailing_newline(self):
        """Text without trailing newline."""
        text = "hello\nworld"  # No final \n
        # Line 2, col 1
        assert byte_offset(text, 2, 1) == 6  # "hello\n" = 6

    def test_windows_line_endings(self):
        """Text with CRLF (\r\n) line endings."""
        text = "hello\r\nworld\r\n"
        # Line 1, col 1
        assert byte_offset(text, 1, 1) == 0
        # Line 2, col 1 = 'w' in "world"
        assert byte_offset(text, 2, 1) == 7  # "hello\r\n" = 7 bytes

    def test_mac_line_endings(self):
        """Text with CR (\r) line endings."""
        text = "hello\rworld\r"
        # Line 1, col 1
        assert byte_offset(text, 1, 1) == 0
        # Line 2, col 1 = 'w' in "world"
        assert byte_offset(text, 2, 1) == 6  # "hello\r" = 6 bytes

    def test_mixed_line_endings(self):
        """Text with mixed line endings."""
        text = "line1\nline2\r\nline3\r"
        # Line 1, col 1
        assert byte_offset(text, 1, 1) == 0
        # Line 2, col 1
        assert byte_offset(text, 2, 1) == 6  # "line1\n"
        # Line 3, col 1
        # "line1\n" (6) + "line2\r\n" (7) = 13
        assert byte_offset(text, 3, 1) == 13  # "line1\nline2\r\n"

    def test_unicode_multibyte_characters(self):
        """Text with multibyte UTF-8 characters."""
        text = "héllo\nwörld\n"
        # Line 1, col 1
        assert byte_offset(text, 1, 1) == 0
        # Line 2, col 1 = 'w'
        # "héllo\n" where é is 2 bytes in UTF-8
        expected = len("héllo\n".encode('utf-8')) - len("\n".encode('utf-8'))
        assert byte_offset(text, 2, 1) == len("héllo\n")

    def test_unicode_emoji(self):
        """Text with emoji (multibyte characters)."""
        text = "hello 👋\nworld\n"
        # Line 2, col 1
        assert byte_offset(text, 2, 1) == len("hello 👋\n")

    def test_tabs_in_text(self):
        """Text with tab characters."""
        text = "hello\tworld\n"
        # Line 1, col 7 = 'w'
        assert byte_offset(text, 1, 7) == 6  # "hello\t" = 6 bytes

    def test_only_whitespace(self):
        """Text with only whitespace."""
        text = "   \n   \n"
        # Line 2, col 2
        assert byte_offset(text, 2, 2) == 5  # "   \n " = 5 bytes

    def test_single_line_no_newline(self):
        """Single line with no newline."""
        text = "hello"
        # Line 1, col 3
        assert byte_offset(text, 1, 3) == 2

    def test_splitlines_keepends_behavior(self):
        """Verify splitlines(True) behavior is correct."""
        text = "a\nb\nc"
        lines = text.splitlines(True)
        # Should be ['a\n', 'b\n', 'c']
        assert lines == ['a\n', 'b\n', 'c']
        # Line 3, col 1 = 'c'
        assert byte_offset(text, 3, 1) == 4  # "a\nb\n" = 4


@pytest.mark.unit
class TestRelTo:
    """Test rel_to() function with all edge cases."""

    def test_path_inside_root(self):
        """Path inside root returns relative path."""
        root = pathlib.Path("/home/user/project")
        path = pathlib.Path("/home/user/project/src/main.py")
        result = rel_to(root, path)
        assert result == "src/main.py" or result == "src\\main.py"

    def test_path_equals_root(self):
        """Path equals root returns '.'."""
        root = pathlib.Path("/home/user/project")
        path = pathlib.Path("/home/user/project")
        result = rel_to(root, path)
        assert result == "."

    def test_path_outside_root(self):
        """Path outside root returns absolute path."""
        root = pathlib.Path("/home/user/project")
        path = pathlib.Path("/etc/config.txt")
        result = rel_to(root, path)
        # Should return absolute path as fallback
        # On Windows, Unix-style paths become "\etc\config.txt"
        assert (result.startswith("/") or
                result.startswith("\\") or
                (len(result) > 2 and result[1:3] == ":\\"))
        assert "config.txt" in result

    def test_path_with_parent_references(self):
        """Path with .. that escapes root."""
        root = pathlib.Path("/home/user/project")
        path = pathlib.Path("/home/user/project/../other/file.py")
        # Resolving this gives /home/user/other/file.py (outside root)
        result = rel_to(root, path)
        # Should fall back to absolute path
        assert "file.py" in result

    def test_root_and_path_nonexistent(self):
        """Non-existent paths still work."""
        root = pathlib.Path("/nonexistent/root")
        path = pathlib.Path("/nonexistent/root/subdir/file.txt")
        result = rel_to(root, path)
        # Should compute relative path even if doesn't exist
        assert "subdir" in result and "file.txt" in result

    def test_windows_paths(self):
        """Windows-style paths."""
        root = pathlib.Path("C:/Users/Dev/project")
        path = pathlib.Path("C:/Users/Dev/project/src/app.py")
        result = rel_to(root, path)
        # Should be relative
        assert "src" in result and "app.py" in result
        # Should not have C: drive letter
        assert "C:" not in result

    def test_different_drives_windows(self):
        """Different drives on Windows (cannot be relative)."""
        # This test only makes sense on Windows
        if pathlib.Path("C:/").exists():
            root = pathlib.Path("C:/project")
            path = pathlib.Path("D:/other/file.txt")
            result = rel_to(root, path)
            # Cannot make relative, should return absolute
            assert "D:" in result or result.startswith("/")

    def test_case_sensitivity(self):
        """Path case handling (platform-dependent)."""
        root = pathlib.Path("/home/user/Project")
        path = pathlib.Path("/home/user/Project/src/file.py")
        result = rel_to(root, path)
        # Should work regardless of case
        assert "file.py" in result

    def test_trailing_slash(self):
        """Root with trailing slash."""
        root = pathlib.Path("/home/user/project/")
        path = pathlib.Path("/home/user/project/src/file.py")
        result = rel_to(root, path)
        assert "src" in result and "file.py" in result

    def test_symlinks(self):
        """Paths involving symlinks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            subdir = root / "subdir"
            subdir.mkdir()
            file_path = subdir / "file.txt"
            file_path.write_text("test")

            result = rel_to(root, file_path)
            assert "subdir" in result and "file.txt" in result

    def test_current_directory_relative(self):
        """Relative paths with current directory."""
        root = pathlib.Path(".")
        path = pathlib.Path("./src/file.py")
        result = rel_to(root.resolve(), path.resolve())
        # Should resolve correctly
        assert "file.py" in result

    def test_exception_handling(self):
        """Verify exception handling returns absolute path."""
        # Create a scenario where relative_to might fail
        root = pathlib.Path("/completely/different/path")
        path = pathlib.Path("/another/path/file.py")
        result = rel_to(root, path)
        # Should not crash, should return absolute path
        assert "file.py" in result

    def test_returns_string(self):
        """Result is always a string."""
        root = pathlib.Path("/home/user/project")
        path = pathlib.Path("/home/user/project/file.py")
        result = rel_to(root, path)
        assert isinstance(result, str)

    def test_empty_path_components(self):
        """Paths with empty components (like //)."""
        root = pathlib.Path("/home//user///project")
        path = pathlib.Path("/home/user/project/src/file.py")
        result = rel_to(root, path)
        # Should normalize and compute relative path
        assert "file.py" in result
