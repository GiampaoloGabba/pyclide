"""Tests for client local commands (list, codemod).

These commands run locally without requiring the server.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Import client for direct testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pyclide"))
from pyclide_client import handle_list, handle_codemod


@pytest.mark.client
class TestListCommand:
    """Test 'list' command (AST-based symbol listing)."""

    def test_list_single_file_with_classes_and_functions(self, tmp_path, capsys):
        """Test listing symbols from a single Python file."""
        test_file = tmp_path / "sample.py"
        test_file.write_text(
            """
class MyClass:
    def method(self):
        pass

def my_function():
    pass

class AnotherClass:
    pass
""",
            encoding="utf-8"
        )

        # Call handle_list
        handle_list([str(test_file.name)], str(tmp_path))

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        # Should have 2 classes and 1 function
        assert len(result) == 3

        # Check classes
        classes = [s for s in result if s["kind"] == "class"]
        assert len(classes) == 2
        assert any(c["name"] == "MyClass" for c in classes)
        assert any(c["name"] == "AnotherClass" for c in classes)

        # Check function
        functions = [s for s in result if s["kind"] == "function"]
        assert len(functions) == 1
        assert functions[0]["name"] == "my_function"

    def test_list_directory_recursive(self, tmp_path, capsys):
        """Test listing symbols from directory (recursive)."""
        # Create multiple files
        (tmp_path / "file1.py").write_text(
            "class ClassA:\n    pass\n",
            encoding="utf-8"
        )
        (tmp_path / "file2.py").write_text(
            "def function_b():\n    pass\n",
            encoding="utf-8"
        )

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file3.py").write_text(
            "class ClassC:\n    pass\n",
            encoding="utf-8"
        )

        # Call handle_list on directory
        handle_list(["."], str(tmp_path))

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        # Should find all 3 symbols
        assert len(result) >= 3

        names = {s["name"] for s in result}
        assert "ClassA" in names
        assert "function_b" in names
        assert "ClassC" in names

    def test_list_empty_file(self, tmp_path, capsys):
        """Test listing symbols from empty file."""
        test_file = tmp_path / "empty.py"
        test_file.write_text("", encoding="utf-8")

        handle_list([str(test_file.name)], str(tmp_path))

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        # Should return empty list
        assert result == []

    def test_list_file_with_syntax_error(self, tmp_path, capsys):
        """Test listing symbols from file with syntax error (should skip)."""
        test_file = tmp_path / "broken.py"
        test_file.write_text("def broken(\n    pass\n", encoding="utf-8")

        handle_list([str(test_file.name)], str(tmp_path))

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        # Should skip file with syntax error
        assert result == []

    def test_list_only_top_level_symbols(self, tmp_path, capsys):
        """Test that only top-level symbols are listed (not nested)."""
        test_file = tmp_path / "nested.py"
        test_file.write_text(
            """
class Outer:
    class Inner:  # Should NOT be listed
        pass

    def method(self):  # Should NOT be listed
        pass

def top_level():
    def nested():  # Should NOT be listed
        pass
""",
            encoding="utf-8"
        )

        handle_list([str(test_file.name)], str(tmp_path))

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        # Should only have 2 top-level symbols
        assert len(result) == 2

        names = {s["name"] for s in result}
        assert "Outer" in names
        assert "top_level" in names
        assert "Inner" not in names
        assert "method" not in names
        assert "nested" not in names

    def test_list_with_line_numbers(self, tmp_path, capsys):
        """Test that line numbers are correct."""
        test_file = tmp_path / "lines.py"
        test_file.write_text(
            """# Line 1: comment
class FirstClass:  # Line 2
    pass

def first_function():  # Line 5
    pass
""",
            encoding="utf-8"
        )

        handle_list([str(test_file.name)], str(tmp_path))

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        # Check line numbers
        class_item = next(s for s in result if s["name"] == "FirstClass")
        assert class_item["line"] == 2

        func_item = next(s for s in result if s["name"] == "first_function")
        assert func_item["line"] == 5

    def test_list_nonexistent_path(self, tmp_path, capsys):
        """Test listing nonexistent path exits with error."""
        with pytest.raises(SystemExit) as exc_info:
            handle_list(["nonexistent.py"], str(tmp_path))

        assert exc_info.value.code == 1


@pytest.mark.client
@pytest.mark.skipif(not shutil.which("ast-grep"), reason="ast-grep not available")
class TestCodemodCommand:
    """Test 'codemod' command (AST transformations via ast-grep)."""

    @pytest.fixture
    def ast_grep_rule(self, tmp_path):
        """Create a simple ast-grep rule file."""
        rule_file = tmp_path / "rule.yml"
        rule_file.write_text(
            """
id: replace-print
language: python
rule:
  pattern: print($MSG)
fix: logger.info($MSG)
""",
            encoding="utf-8"
        )
        return rule_file

    def test_codemod_dry_run(self, tmp_path, ast_grep_rule, capsys):
        """Test codemod in dry-run mode (no --apply)."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            'print("Hello")\nprint("World")\n',
            encoding="utf-8"
        )

        # Temporarily modify sys.argv to not include --apply
        original_argv = sys.argv
        try:
            sys.argv = ["pyclide_client.py", "codemod", str(ast_grep_rule)]

            handle_codemod([str(ast_grep_rule)], str(tmp_path))

            captured = capsys.readouterr()
            result = json.loads(captured.out)

            # Should have output
            assert "stdout" in result
            assert "returncode" in result
            assert result["applied"] is False

            # File should NOT be modified
            assert test_file.read_text() == 'print("Hello")\nprint("World")\n'

        finally:
            sys.argv = original_argv

    def test_codemod_with_apply(self, tmp_path, ast_grep_rule, capsys):
        """Test codemod with --apply flag."""
        test_file = tmp_path / "test.py"
        original_content = 'print("Hello")\n'
        test_file.write_text(original_content, encoding="utf-8")

        # Temporarily modify sys.argv to include --apply
        original_argv = sys.argv
        try:
            sys.argv = ["pyclide_client.py", "codemod", str(ast_grep_rule), "--apply"]

            handle_codemod([str(ast_grep_rule)], str(tmp_path))

            captured = capsys.readouterr()
            result = json.loads(captured.out)

            assert result["applied"] is True
            assert result["returncode"] in (0, 2)  # 0 = matches, 2 = no matches

        finally:
            sys.argv = original_argv

    def test_codemod_with_invalid_rule(self, tmp_path, capsys):
        """Test codemod with invalid YAML rule."""
        bad_rule = tmp_path / "bad_rule.yml"
        bad_rule.write_text("invalid: [yaml structure", encoding="utf-8")

        original_argv = sys.argv
        try:
            sys.argv = ["pyclide_client.py", "codemod", str(bad_rule)]

            # ast-grep might return error in stderr but still exit 0 or 2
            # We just verify the command completes and check stderr for errors
            handle_codemod([str(bad_rule)], str(tmp_path))

            captured = capsys.readouterr()
            result = json.loads(captured.out)

            # Should have error in stderr (ast-grep reports issues there)
            assert "stderr" in result
            assert len(result["stderr"]) > 0  # Some error message present

        finally:
            sys.argv = original_argv

    def test_codemod_output_format(self, tmp_path, ast_grep_rule, capsys):
        """Test that codemod returns JSON with expected fields."""
        test_file = tmp_path / "test.py"
        test_file.write_text('print("test")\n', encoding="utf-8")

        original_argv = sys.argv
        try:
            sys.argv = ["pyclide_client.py", "codemod", str(ast_grep_rule)]

            handle_codemod([str(ast_grep_rule)], str(tmp_path))

            captured = capsys.readouterr()
            result = json.loads(captured.out)

            # Check required fields
            assert "stdout" in result
            assert "stderr" in result
            assert "returncode" in result
            assert "applied" in result

            assert isinstance(result["stdout"], str)
            assert isinstance(result["stderr"], str)
            assert isinstance(result["returncode"], int)
            assert isinstance(result["applied"], bool)

        finally:
            sys.argv = original_argv


@pytest.mark.client
class TestCodemodWithoutAstGrep:
    """Test codemod behavior when ast-grep is not available."""

    def test_codemod_missing_ast_grep(self, tmp_path, monkeypatch):
        """Test that codemod exits gracefully when ast-grep is missing."""
        # Mock shutil.which to return None (ast-grep not found)
        monkeypatch.setattr(shutil, "which", lambda x: None)

        rule_file = tmp_path / "rule.yml"
        rule_file.write_text("id: test\n", encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            handle_codemod([str(rule_file)], str(tmp_path))

        # Should exit with error code
        assert exc_info.value.code == 1
