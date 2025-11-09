"""Tests for utility features (list globals, AST parsing, etc)."""

import ast
import pathlib
import sys

import pytest

# Add parent directory to path to import pyclide
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pyclide import rel_to, byte_offset


class TestUtilities:
    """Test utility functions."""

    @pytest.fixture
    def fixtures_dir(self):
        """Return the fixtures directory path."""
        return pathlib.Path(__file__).parent / "fixtures"

    @pytest.fixture
    def sample_module_path(self, fixtures_dir):
        """Return path to sample_module.py."""
        return fixtures_dir / "sample_module.py"

    def test_rel_to_same_directory(self):
        """Test relative path calculation in same directory."""
        root = pathlib.Path("/home/user/project")
        path = pathlib.Path("/home/user/project/file.py")
        result = rel_to(root, path)
        assert result == "file.py"

    def test_rel_to_subdirectory(self):
        """Test relative path calculation in subdirectory."""
        root = pathlib.Path("/home/user/project")
        path = pathlib.Path("/home/user/project/src/main.py")
        result = rel_to(root, path)
        assert result == "src/main.py" or result == r"src\main.py"

    def test_rel_to_outside_root(self):
        """Test relative path calculation outside root."""
        root = pathlib.Path("/home/user/project")
        path = pathlib.Path("/home/other/file.py")
        result = rel_to(root, path)
        # Should return absolute path as string when not relative
        assert str(path) in result

    def test_byte_offset_first_line(self):
        """Test byte offset calculation on first line."""
        text = "hello world\nsecond line\n"
        # Line 1, column 1 (first character)
        offset = byte_offset(text, 1, 1)
        assert offset == 0

        # Line 1, column 7 (should be at 'w' in world)
        offset = byte_offset(text, 1, 7)
        assert offset == 6

    def test_byte_offset_second_line(self):
        """Test byte offset calculation on second line."""
        text = "hello world\nsecond line\n"
        # Line 2, column 1 (first character of second line)
        offset = byte_offset(text, 2, 1)
        assert offset == 12  # After "hello world\n"

        # Line 2, column 8 (should be at 'l' in "line")
        offset = byte_offset(text, 2, 8)
        assert offset == 19

    def test_byte_offset_multiline(self):
        """Test byte offset with multiple lines."""
        text = "line1\nline2\nline3\n"
        # Line 3, column 1
        offset = byte_offset(text, 3, 1)
        assert offset == 12  # After "line1\nline2\n"

    def test_list_globals_functions(self, sample_module_path):
        """Test listing global functions from a file."""
        tree = ast.parse(sample_module_path.read_text(encoding="utf-8"))

        functions = [
            node.name for node in tree.body if isinstance(node, ast.FunctionDef)
        ]

        assert "hello_world" in functions
        assert "calculate_sum" in functions

    def test_list_globals_classes(self, sample_module_path):
        """Test listing global classes from a file."""
        tree = ast.parse(sample_module_path.read_text(encoding="utf-8"))

        classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]

        assert "Calculator" in classes
        assert "AdvancedCalculator" in classes

    def test_list_globals_with_line_numbers(self, sample_module_path):
        """Test that AST nodes have line numbers."""
        tree = ast.parse(sample_module_path.read_text(encoding="utf-8"))

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                assert hasattr(node, "lineno")
                assert node.lineno > 0

                if node.name == "hello_world":
                    # hello_world should be around line 4
                    assert node.lineno == 4

                if node.name == "Calculator":
                    # Calculator class should be around line 24
                    assert node.lineno == 24


class TestSimpleGrep:
    """Test simple text search functionality."""

    @pytest.fixture
    def fixtures_dir(self):
        """Return the fixtures directory path."""
        return pathlib.Path(__file__).parent / "fixtures"

    def test_simple_text_search(self, fixtures_dir):
        """Test simple pattern matching in files."""
        pattern = "Calculator"
        hits = []

        for p in fixtures_dir.rglob("*.py"):
            try:
                for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    if pattern in line:
                        hits.append({"path": p.name, "line": i, "column": line.find(pattern) + 1})
            except Exception:
                pass

        # Should find Calculator in both files
        assert len(hits) >= 2

        # Check that we found it in sample_module.py
        paths = [h["path"] for h in hits]
        assert "sample_module.py" in paths

    def test_search_function_definition(self, fixtures_dir):
        """Test searching for function definition pattern."""
        pattern = "def hello_world"
        hits = []

        for p in fixtures_dir.rglob("*.py"):
            try:
                for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    if pattern in line:
                        hits.append({"path": p.name, "line": i})
            except Exception:
                pass

        # Should find the function definition
        assert len(hits) >= 1
        assert any(h["path"] == "sample_module.py" for h in hits)

    def test_search_import_statement(self, fixtures_dir):
        """Test searching for import statements."""
        pattern = "from sample_module import"
        hits = []

        for p in fixtures_dir.rglob("*.py"):
            try:
                for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    if pattern in line:
                        hits.append({"path": p.name, "line": i})
            except Exception:
                pass

        # Should find the import in sample_usage.py
        assert any(h["path"] == "sample_usage.py" for h in hits)


class TestMaybeJson:
    """Test maybe_json utility function."""

    def test_maybe_json_with_json_out_true_dict(self, capsys):
        """Test maybe_json with json_out=True and dict input."""
        from pyclide import maybe_json
        import json

        data = {"key1": "value1", "key2": 42}
        maybe_json(data, json_out=True)

        captured = capsys.readouterr()
        # Should be valid JSON
        parsed = json.loads(captured.out)
        assert parsed == data

    def test_maybe_json_with_json_out_true_list(self, capsys):
        """Test maybe_json with json_out=True and list input."""
        from pyclide import maybe_json
        import json

        data = [{"name": "foo"}, {"name": "bar"}]
        maybe_json(data, json_out=True)

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == data

    def test_maybe_json_with_json_out_false_dict(self, capsys):
        """Test maybe_json with json_out=False and dict input."""
        from pyclide import maybe_json

        data = {"file1.py": "content1", "file2.py": "content2"}
        maybe_json(data, json_out=False)

        captured = capsys.readouterr()
        # Should have formatted output with keys in brackets
        assert "[file1.py]" in captured.out
        assert "content1" in captured.out
        assert "[file2.py]" in captured.out
        assert "content2" in captured.out

    def test_maybe_json_with_json_out_false_list(self, capsys):
        """Test maybe_json with json_out=False and list input."""
        from pyclide import maybe_json

        data = [{"name": "item1", "line": 10}, {"name": "item2", "line": 20}]
        maybe_json(data, json_out=False)

        captured = capsys.readouterr()
        # Should print each item as JSON on separate lines
        lines = captured.out.strip().split("\n")
        assert len(lines) == 2
        assert "item1" in lines[0]
        assert "item2" in lines[1]

    def test_maybe_json_preserves_non_ascii(self, capsys):
        """Test that maybe_json preserves non-ASCII characters."""
        from pyclide import maybe_json
        import json

        data = {"message": "Héllo Wörld 你好"}
        maybe_json(data, json_out=True)

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["message"] == "Héllo Wörld 你好"


class TestConfirmApply:
    """Test confirm_apply utility function."""

    def test_confirm_apply_with_force_true(self):
        """Test that force=True returns True immediately."""
        from pyclide import confirm_apply

        result = confirm_apply(force=True)
        assert result is True

    def test_confirm_apply_with_user_input_y(self, monkeypatch):
        """Test that user input 'y' returns True."""
        from pyclide import confirm_apply
        from io import StringIO

        # Mock stdin to return 'y'
        monkeypatch.setattr('sys.stdin', StringIO('y\n'))
        result = confirm_apply(force=False)
        assert result is True

    def test_confirm_apply_with_user_input_yes(self, monkeypatch):
        """Test that user input 'yes' returns True."""
        from pyclide import confirm_apply
        from io import StringIO

        monkeypatch.setattr('sys.stdin', StringIO('yes\n'))
        result = confirm_apply(force=False)
        assert result is True

    def test_confirm_apply_with_user_input_n(self, monkeypatch):
        """Test that user input 'n' returns False."""
        from pyclide import confirm_apply
        from io import StringIO

        monkeypatch.setattr('sys.stdin', StringIO('n\n'))
        result = confirm_apply(force=False)
        assert result is False

    def test_confirm_apply_with_user_input_empty(self, monkeypatch):
        """Test that empty input returns False."""
        from pyclide import confirm_apply
        from io import StringIO

        monkeypatch.setattr('sys.stdin', StringIO('\n'))
        result = confirm_apply(force=False)
        assert result is False

    def test_confirm_apply_with_user_input_no(self, monkeypatch):
        """Test that 'no' input returns False."""
        from pyclide import confirm_apply
        from io import StringIO

        monkeypatch.setattr('sys.stdin', StringIO('no\n'))
        result = confirm_apply(force=False)
        assert result is False


class TestEnsure:
    """Test ensure utility function."""

    def test_ensure_with_true_condition(self):
        """Test that ensure does nothing when condition is True."""
        from pyclide import ensure

        # Should not raise or exit
        ensure(True, "This should not be printed")
        # If we get here, test passes

    def test_ensure_with_false_condition(self):
        """Test that ensure exits with code 2 when condition is False."""
        from pyclide import ensure
        import typer

        with pytest.raises(typer.Exit) as exc_info:
            ensure(False, "Error message")

        # Check exit code is 2
        assert exc_info.value.exit_code == 2

    def test_ensure_prints_error_message(self, capsys):
        """Test that ensure prints error message to stderr."""
        from pyclide import ensure
        import typer

        with pytest.raises(typer.Exit):
            ensure(False, "Custom error message")

        # Check that message was printed to stderr
        captured = capsys.readouterr()
        assert "Custom error message" in captured.err


class TestJediToLocations:
    """Test jedi_to_locations utility function."""

    def test_jedi_to_locations_empty_list(self):
        """Test with empty list returns empty list."""
        from pyclide import jedi_to_locations

        result = jedi_to_locations([])
        assert result == []

    def test_jedi_to_locations_valid_definitions(self):
        """Test with valid Jedi definitions."""
        from pyclide import jedi_to_locations

        # Create mock Jedi definition objects
        class MockDef:
            def __init__(self, name, type_, module_path, line, column):
                self.name = name
                self.type = type_
                self.module_path = module_path
                self.line = line
                self.column = column

        defs = [
            MockDef("foo", "function", "/path/to/file.py", 10, 5),
            MockDef("Bar", "class", "/path/to/other.py", 20, 1),
        ]

        result = jedi_to_locations(defs)

        assert len(result) == 2
        assert result[0]["name"] == "foo"
        assert result[0]["type"] == "function"
        assert result[0]["path"] == "/path/to/file.py"
        assert result[0]["line"] == 10
        assert result[0]["column"] == 5

        assert result[1]["name"] == "Bar"
        assert result[1]["type"] == "class"
        assert result[1]["path"] == "/path/to/other.py"
        assert result[1]["line"] == 20
        assert result[1]["column"] == 1

    def test_jedi_to_locations_skip_without_module_path(self):
        """Test that definitions without module_path are skipped."""
        from pyclide import jedi_to_locations

        class MockDef:
            def __init__(self, name, line):
                self.name = name
                self.module_path = None  # Missing module_path
                self.line = line
                self.type = "function"

        defs = [MockDef("foo", 10)]
        result = jedi_to_locations(defs)

        # Should skip this definition
        assert len(result) == 0

    def test_jedi_to_locations_skip_without_line(self):
        """Test that definitions without line are skipped."""
        from pyclide import jedi_to_locations

        class MockDef:
            def __init__(self, name, module_path):
                self.name = name
                self.module_path = module_path
                self.line = None  # Missing line
                self.type = "function"

        defs = [MockDef("foo", "/path/to/file.py")]
        result = jedi_to_locations(defs)

        # Should skip this definition
        assert len(result) == 0

    def test_jedi_to_locations_default_column(self):
        """Test that column defaults to 1 if not provided."""
        from pyclide import jedi_to_locations

        class MockDef:
            def __init__(self):
                self.name = "foo"
                self.module_path = "/path/to/file.py"
                self.line = 10
                self.column = None  # No column
                self.type = "function"

        defs = [MockDef()]
        result = jedi_to_locations(defs)

        assert len(result) == 1
        assert result[0]["column"] == 1  # Should default to 1
