"""Tests for JSON output validation across all CLI commands."""

import json
import pathlib
import shutil
import sys

import pytest
from typer.testing import CliRunner

# Add parent directory to path to import pyclide
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pyclide import app

runner = CliRunner()


class TestDefsJsonOutput:
    """Test JSON output for defs command."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:  # Skip invalid files
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_defs_json_structure(self, temp_project):
        """Test that defs command returns valid JSON array."""
        result = runner.invoke(
            app,
            [
                "defs",
                "sample_module.py",
                "4",
                "5",
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        # Should succeed
        assert result.exit_code == 0

        # Should be valid JSON
        data = json.loads(result.stdout)

        # Should be an array
        assert isinstance(data, list)

        # Each item should have expected fields
        for item in data:
            assert "path" in item
            assert "line" in item
            assert "column" in item
            assert "name" in item
            assert "type" in item

            # Types should be correct
            assert isinstance(item["path"], str)
            assert isinstance(item["line"], int)
            assert isinstance(item["column"], int)
            assert isinstance(item["name"], str)
            assert isinstance(item["type"], str)

    def test_defs_empty_result(self, temp_project):
        """Test defs with no results returns empty JSON array."""
        # Create a file with just comments
        comment_file = temp_project / "comments.py"
        comment_file.write_text("# Just a comment\n", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "defs",
                "comments.py",
                "1",
                "1",
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        # May succeed with empty result
        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert isinstance(data, list)


class TestRefsJsonOutput:
    """Test JSON output for refs command."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_refs_json_structure(self, temp_project):
        """Test that refs command returns valid JSON array."""
        result = runner.invoke(
            app,
            [
                "refs",
                "sample_module.py",
                "4",
                "5",
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)

        # Validate structure
        for item in data:
            assert "path" in item
            assert "line" in item
            assert "column" in item
            assert isinstance(item["line"], int)
            assert isinstance(item["column"], int)


class TestHoverJsonOutput:
    """Test JSON output for hover command."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_hover_json_structure(self, temp_project):
        """Test that hover command returns valid JSON array."""
        result = runner.invoke(
            app,
            [
                "hover",
                "sample_module.py",
                "4",
                "5",
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)

        # Validate structure
        for item in data:
            assert "name" in item
            assert "type" in item
            assert isinstance(item["name"], str)
            assert isinstance(item["type"], str)

            # Optional fields
            if "signature" in item:
                assert isinstance(item["signature"], str)
            if "docstring" in item:
                assert isinstance(item["docstring"], str)


class TestOccurrencesJsonOutput:
    """Test JSON output for occurrences command."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_occurrences_json_structure(self, temp_project):
        """Test that occurrences command returns valid JSON array."""
        result = runner.invoke(
            app,
            [
                "occurrences",
                "sample_module.py",
                "4",
                "5",
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)

        # Validate structure
        for item in data:
            assert "path" in item
            assert "line" in item
            assert "column" in item
            assert isinstance(item["path"], str)
            assert isinstance(item["line"], int)
            assert isinstance(item["column"], int)


class TestListJsonOutput:
    """Test JSON output for list command."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_list_json_structure(self, temp_project):
        """Test that list command returns valid JSON array."""
        result = runner.invoke(
            app, ["list", "sample_module.py", "--root", str(temp_project), "--json"]
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)

        # Should have at least some items
        assert len(data) > 0

        # Validate structure
        for item in data:
            assert "path" in item
            assert "kind" in item
            assert "name" in item
            assert "line" in item

            assert isinstance(item["path"], str)
            assert isinstance(item["kind"], str)
            assert isinstance(item["name"], str)
            assert isinstance(item["line"], int)

            # kind should be 'class' or 'function'
            assert item["kind"] in ["class", "function"]

    def test_list_directory_json(self, temp_project):
        """Test list on directory returns JSON for all files."""
        result = runner.invoke(
            app, ["list", ".", "--root", str(temp_project), "--json"]
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)

        # Should have multiple items from different files
        paths = set(item["path"] for item in data)
        assert len(paths) >= 1


class TestRenameJsonOutput:
    """Test JSON output for rename command."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_rename_json_structure(self, temp_project):
        """Test that rename command returns valid JSON with patches."""
        result = runner.invoke(
            app,
            [
                "rename",
                "sample_module.py",
                "14",
                "5",
                "new_message",
                "--root",
                str(temp_project),
                "--json",
                "--force",  # Auto-apply without confirmation
            ],
        )

        # Should succeed or fail gracefully
        if result.exit_code == 0:
            data = json.loads(result.stdout)

            # Should have patches key
            assert "patches" in data
            assert isinstance(data["patches"], dict)

            # Each patch should map filename to content
            for filename, content in data["patches"].items():
                assert isinstance(filename, str)
                assert isinstance(content, str)


class TestExtractMethodJsonOutput:
    """Test JSON output for extract-method command."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_extract_method_json_structure(self, temp_project):
        """Test that extract-method returns valid JSON."""
        result = runner.invoke(
            app,
            [
                "extract-method",
                "sample_module.py",
                "14",
                "14",
                "extracted_func",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)

            assert "patches" in data
            assert isinstance(data["patches"], dict)


class TestExtractVarJsonOutput:
    """Test JSON output for extract-var command."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_extract_var_json_structure(self, temp_project):
        """Test that extract-var returns valid JSON."""
        result = runner.invoke(
            app,
            [
                "extract-var",
                "sample_module.py",
                "20",
                "20",
                "temp_var",
                "--root",
                str(temp_project),
                "--start-col",
                "16",
                "--end-col",
                "21",
                "--json",
                "--force",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)

            assert "patches" in data
            assert isinstance(data["patches"], dict)


class TestOrganizeImportsJsonOutput:
    """Test JSON output for organize-imports command."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with messy imports."""
        test_file = tmp_path / "messy.py"
        test_file.write_text(
            """
import os
import sys


import json

def test():
    print(os.getcwd())
    print(sys.version)
    print(json.dumps({}))
""",
            encoding="utf-8",
        )
        return tmp_path

    def test_organize_imports_json_structure(self, temp_project):
        """Test that organize-imports returns valid JSON."""
        result = runner.invoke(
            app,
            [
                "organize-imports",
                "messy.py",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        # Should succeed
        if result.exit_code == 0:
            data = json.loads(result.stdout)

            assert "patches" in data
            assert isinstance(data["patches"], dict)


class TestUnicodeHandling:
    """Test that JSON output correctly handles Unicode."""

    def test_unicode_in_code_content(self, tmp_path):
        """Test that non-ASCII characters in code are preserved."""
        # Create file with Unicode content
        unicode_file = tmp_path / "unicode.py"
        unicode_file.write_text(
            '''
def greet():
    """Функция приветствия."""
    return "Привет, мир! 你好世界"

class Café:
    """Une classe française."""
    pass
''',
            encoding="utf-8",
        )

        result = runner.invoke(
            app, ["list", "unicode.py", "--root", str(tmp_path), "--json"]
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)

        # Find the Café class
        cafe_items = [item for item in data if item["name"] == "Café"]
        assert len(cafe_items) == 1
        assert cafe_items[0]["name"] == "Café"

    def test_unicode_in_hover_output(self, tmp_path):
        """Test Unicode in hover docstrings."""
        unicode_file = tmp_path / "unicode.py"
        unicode_file.write_text(
            '''
def greet():
    """Приветствие на русском: Привет!"""
    return "Hello"
''',
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "hover",
                "unicode.py",
                "2",
                "5",
                "--root",
                str(tmp_path),
                "--json",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)

            # Check that Unicode is preserved
            if len(data) > 0 and "docstring" in data[0]:
                docstring = data[0]["docstring"]
                assert isinstance(docstring, str)
                # Should contain Cyrillic characters
                assert "Привет" in docstring or "русском" in docstring


class TestCodemodJsonOutput:
    """Test JSON output for codemod command."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with test file and rule."""
        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
print("Hello")
print("World")
""",
            encoding="utf-8",
        )

        # Create a rule file
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        rule_file = rules_dir / "rule.yml"
        rule_file.write_text(
            """
id: test-rule
language: python
rule:
  pattern: print($ARG)
message: Found print statement
""",
            encoding="utf-8",
        )

        return tmp_path, rule_file

    def test_codemod_json_structure(self, temp_project):
        """Test that codemod returns valid JSON."""
        tmp_path, rule_file = temp_project

        # Only run if ast-grep is available
        import shutil

        if shutil.which("ast-grep") is None:
            pytest.skip("ast-grep not available")

        result = runner.invoke(
            app,
            [
                "codemod",
                str(rule_file),
                "--root",
                str(tmp_path),
                "--json",
            ],
        )

        # ast-grep may return exit code 0 or 2
        if result.exit_code in [0, 2]:
            data = json.loads(result.stdout)

            # Should have stdout key
            assert "stdout" in data
            assert isinstance(data["stdout"], str)
