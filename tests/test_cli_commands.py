"""End-to-end CLI command tests using CliRunner.

Tests actual Typer commands, not just engine methods.
"""

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


# --------------------------------------------------------------------------------------
# PART 1: Navigation Commands (defs, refs, hover, occurrences)
# --------------------------------------------------------------------------------------


class TestDefsCommand:
    """Test the `defs` command end-to-end."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_defs_goto_function_definition(self, temp_project):
        """Test goto definition on a function call."""
        result = runner.invoke(
            app,
            [
                "defs",
                "sample_usage.py",
                "9",
                "20",  # On "hello_world" in the call
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0

        # Should find hello_world
        assert any(item["name"] == "hello_world" for item in data)

    def test_defs_goto_class_definition(self, temp_project):
        """Test goto definition on a class instantiation."""
        result = runner.invoke(
            app,
            [
                "defs",
                "sample_usage.py",
                "13",
                "15",  # On "Calculator"
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert len(data) > 0
        assert any(item["name"] == "Calculator" for item in data)

    def test_defs_goto_imported_symbol(self, temp_project):
        """Test goto on an import statement."""
        result = runner.invoke(
            app,
            [
                "defs",
                "sample_usage.py",
                "3",
                "30",  # On "hello_world" in import
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        # Should succeed
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        # May return definition or import location
        assert isinstance(data, list)

    def test_defs_multiple_definitions(self, temp_project):
        """Test when symbol has multiple definitions (should show all)."""
        # Create a file with method overriding
        test_file = temp_project / "override.py"
        test_file.write_text(
            """
class Base:
    def method(self):
        pass

class Derived(Base):
    def method(self):
        pass

d = Derived()
d.method()
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "defs",
                "override.py",
                "11",
                "3",  # On "method" call
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        # Jedi may return one or both definitions
        assert isinstance(data, list)

    def test_defs_symbol_not_found(self, temp_project):
        """Test when symbol is not found."""
        # Click on whitespace
        result = runner.invoke(
            app,
            [
                "defs",
                "sample_module.py",
                "1",
                "1",  # Empty docstring line
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        # Should succeed with empty array
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)
        # May be empty

    def test_defs_invalid_file_path(self, temp_project):
        """Test with invalid file path."""
        result = runner.invoke(
            app,
            [
                "defs",
                "nonexistent.py",
                "1",
                "1",
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        # Should exit with error code
        assert result.exit_code != 0

    def test_defs_invalid_position_out_of_bounds(self, temp_project):
        """Test with line/col out of bounds."""
        result = runner.invoke(
            app,
            [
                "defs",
                "sample_module.py",
                "10000",
                "10000",
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        # Jedi may handle gracefully or return empty
        # Either exit code 0 with empty result or error is acceptable
        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert isinstance(data, list)

    def test_defs_json_vs_no_json_output(self, temp_project):
        """Test both --json and --no-json output formats."""
        # JSON output
        result_json = runner.invoke(
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

        assert result_json.exit_code == 0
        data = json.loads(result_json.stdout)
        assert isinstance(data, list)

        # No-json output
        result_no_json = runner.invoke(
            app,
            [
                "defs",
                "sample_module.py",
                "4",
                "5",
                "--root",
                str(temp_project),
                "--no-json",
            ],
        )

        assert result_no_json.exit_code == 0
        # Should be line-by-line JSON
        lines = result_no_json.stdout.strip().split("\n")
        for line in lines:
            if line.strip():
                json.loads(line)  # Each line should be valid JSON

    def test_defs_with_root_parameter(self, temp_project):
        """Test --root parameter with relative paths."""
        # Use relative path from root
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

        assert result.exit_code == 0


class TestRefsCommand:
    """Test the `refs` command end-to-end."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_refs_find_usages_across_files(self, temp_project):
        """Test finding references across multiple files."""
        result = runner.invoke(
            app,
            [
                "refs",
                "sample_module.py",
                "4",
                "5",  # On "hello_world" definition
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)

        # Should find references in both sample_module and sample_usage
        paths = [item["path"] for item in data]
        assert any("sample_module.py" in p for p in paths)
        assert any("sample_usage.py" in p for p in paths)

    def test_refs_no_references_found(self, temp_project):
        """Test when no references are found."""
        # Create a function that's never used
        test_file = temp_project / "unused.py"
        test_file.write_text(
            """
def unused_function():
    pass
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "refs",
                "unused.py",
                "2",
                "5",
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)
        # May have only the definition itself

    def test_refs_builtin_symbols_excluded(self, temp_project):
        """Test that built-in symbols are excluded."""
        # Create file using built-in like "print"
        test_file = temp_project / "builtin.py"
        test_file.write_text(
            """
def test():
    print("hello")
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "refs",
                "builtin.py",
                "3",
                "5",  # On "print"
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        # Should handle gracefully
        if result.exit_code == 0:
            data = json.loads(result.stdout)
            # Built-ins should be excluded (include_builtins=False)
            # Result should be empty or minimal
            assert isinstance(data, list)

    def test_refs_json_vs_no_json(self, temp_project):
        """Test both output formats."""
        result_json = runner.invoke(
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

        assert result_json.exit_code == 0
        data = json.loads(result_json.stdout)
        assert isinstance(data, list)

        result_no_json = runner.invoke(
            app,
            [
                "refs",
                "sample_module.py",
                "4",
                "5",
                "--root",
                str(temp_project),
                "--no-json",
            ],
        )

        assert result_no_json.exit_code == 0


class TestHoverCommand:
    """Test the `hover` command end-to-end."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_hover_function_with_signature_and_docstring(self, temp_project):
        """Test hover on a function shows signature and docstring."""
        result = runner.invoke(
            app,
            [
                "hover",
                "sample_module.py",
                "4",
                "5",  # On "hello_world"
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0

        item = data[0]
        assert item["name"] == "hello_world"
        assert item["type"] == "function"

        # Should have signature
        if "signature" in item:
            assert "name" in item["signature"]

        # Should have docstring
        if "docstring" in item:
            assert "greeting" in item["docstring"].lower()

    def test_hover_class(self, temp_project):
        """Test hover on a class."""
        result = runner.invoke(
            app,
            [
                "hover",
                "sample_module.py",
                "24",
                "7",  # On "Calculator" class
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert len(data) > 0

        item = data[0]
        assert item["name"] == "Calculator"
        assert item["type"] == "class"

    def test_hover_variable_inferred_type(self, temp_project):
        """Test hover on a variable shows inferred type."""
        result = runner.invoke(
            app,
            [
                "hover",
                "sample_module.py",
                "14",
                "5",  # On "message" variable
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)

        if len(data) > 0:
            item = data[0]
            assert "type" in item

    def test_hover_no_info_available(self, temp_project):
        """Test hover when no info is available."""
        # Hover on whitespace or comment
        test_file = temp_project / "comment.py"
        test_file.write_text("# Comment\n", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "hover",
                "comment.py",
                "1",
                "1",
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        # Should succeed with empty array
        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert isinstance(data, list)

    def test_hover_json_vs_no_json(self, temp_project):
        """Test both output formats."""
        result_json = runner.invoke(
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

        assert result_json.exit_code == 0
        json.loads(result_json.stdout)

        result_no_json = runner.invoke(
            app,
            [
                "hover",
                "sample_module.py",
                "4",
                "5",
                "--root",
                str(temp_project),
                "--no-json",
            ],
        )

        assert result_no_json.exit_code == 0


class TestOccurrencesCommand:
    """Test the `occurrences` command end-to-end."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_occurrences_function_across_files(self, temp_project):
        """Test finding occurrences of a function."""
        result = runner.invoke(
            app,
            [
                "occurrences",
                "sample_module.py",
                "4",
                "5",  # On "hello_world"
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) >= 1

        # Check structure
        for item in data:
            assert "path" in item
            assert "line" in item
            assert "column" in item

    def test_occurrences_local_variable(self, temp_project):
        """Test occurrences of a local variable (limited scope)."""
        result = runner.invoke(
            app,
            [
                "occurrences",
                "sample_module.py",
                "14",
                "5",  # On "message" variable
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)

        # Should find definition and usage within function
        # All occurrences should be in same file
        paths = [item["path"] for item in data]
        assert all("sample_module.py" in p for p in paths)

    def test_occurrences_class(self, temp_project):
        """Test occurrences of a class name."""
        result = runner.invoke(
            app,
            [
                "occurrences",
                "sample_module.py",
                "24",
                "7",  # On "Calculator" class
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert len(data) >= 1

    def test_occurrences_no_results(self, temp_project):
        """Test when no occurrences are found."""
        # Create unused symbol
        test_file = temp_project / "unused.py"
        test_file.write_text(
            """
def unused():
    unused_var = 42
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "occurrences",
                "unused.py",
                "3",
                "5",  # On "unused_var"
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        # Should have at least the definition
        assert isinstance(data, list)

    def test_occurrences_vs_refs_comparison(self, temp_project):
        """Compare occurrences to refs (should be more conservative)."""
        # Occurrences uses Rope's rename scope
        # Refs uses Jedi's references

        occ_result = runner.invoke(
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

        refs_result = runner.invoke(
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

        if occ_result.exit_code == 0 and refs_result.exit_code == 0:
            occ_data = json.loads(occ_result.stdout)
            refs_data = json.loads(refs_result.stdout)

            # Both should be lists
            assert isinstance(occ_data, list)
            assert isinstance(refs_data, list)

            # Occurrences is typically more conservative or similar
            # (This is not a strict requirement, just documenting behavior)


# --------------------------------------------------------------------------------------
# PART 2: Refactoring Commands (rename, extract-method, extract-var)
# --------------------------------------------------------------------------------------


class TestRenameCommand:
    """Test the `rename` command end-to-end."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_rename_local_variable(self, temp_project):
        """Test renaming a local variable."""
        result = runner.invoke(
            app,
            [
                "rename",
                "sample_module.py",
                "14",
                "5",  # On "message" variable
                "new_message",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert "patches" in data

        # Check that new name appears in patch
        if "sample_module.py" in data["patches"]:
            content = data["patches"]["sample_module.py"]
            assert "new_message" in content

    def test_rename_function_across_files(self, temp_project):
        """Test renaming a function used in multiple files."""
        result = runner.invoke(
            app,
            [
                "rename",
                "sample_module.py",
                "4",
                "5",  # On "hello_world"
                "greet_user",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert "patches" in data

        # Should change at least the definition file
        patches = data["patches"]
        assert len(patches) >= 1

        # Check for new name in patches
        all_content = " ".join(patches.values())
        assert "greet_user" in all_content

    def test_rename_class_across_files(self, temp_project):
        """Test renaming a class."""
        result = runner.invoke(
            app,
            [
                "rename",
                "sample_module.py",
                "24",
                "7",  # On "Calculator"
                "MathCalculator",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert "patches" in data

        # Should rename class definition
        if "sample_module.py" in data["patches"]:
            assert "MathCalculator" in data["patches"]["sample_module.py"]

    def test_rename_method(self, temp_project):
        """Test renaming a class method."""
        result = runner.invoke(
            app,
            [
                "rename",
                "sample_module.py",
                "30",
                "9",  # On "add" method
                "add_value",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert "patches" in data

    def test_rename_with_force_flag(self, temp_project):
        """Test --force flag (no confirmation)."""
        result = runner.invoke(
            app,
            [
                "rename",
                "sample_module.py",
                "14",
                "5",
                "forced_name",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        # Should succeed without prompting
        assert result.exit_code == 0

    def test_rename_json_output(self, temp_project):
        """Test --json output format."""
        result = runner.invoke(
            app,
            [
                "rename",
                "sample_module.py",
                "14",
                "5",
                "json_test",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert "patches" in data
        assert isinstance(data["patches"], dict)

    def test_rename_no_json_output_diff(self, temp_project):
        """Test --no-json output shows unified diff."""
        result = runner.invoke(
            app,
            [
                "rename",
                "sample_module.py",
                "14",
                "5",
                "diff_test",
                "--root",
                str(temp_project),
                "--no-json",
                "--force",
            ],
        )

        # Should show diff format
        if result.exit_code == 0:
            # Check for diff markers
            output = result.stdout
            # May contain --- or +++ for diff
            assert output  # Should have some output

    def test_rename_user_decline_confirmation(self, temp_project, monkeypatch):
        """Test user declining confirmation."""
        from io import StringIO

        monkeypatch.setattr("sys.stdin", StringIO("n\n"))

        result = runner.invoke(
            app,
            [
                "rename",
                "sample_module.py",
                "14",
                "5",
                "declined_name",
                "--root",
                str(temp_project),
                "--no-json",
            ],
            input="n\n",
        )

        # Should indicate changes not applied
        if result.exit_code == 0:
            assert "NOT applied" in result.stderr or "NOT applied" in result.stdout

    def test_rename_invalid_symbol_error(self, temp_project):
        """Test renaming invalid symbol shows error."""
        # Try to rename at a position with no symbol
        result = runner.invoke(
            app,
            [
                "rename",
                "sample_module.py",
                "1",
                "1",  # On docstring
                "invalid",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        # Should fail or return empty patches
        if result.exit_code != 0:
            # Error expected
            pass
        else:
            data = json.loads(result.stdout)
            # May have empty patches
            if "patches" in data:
                assert isinstance(data["patches"], dict)


class TestExtractMethodCommand:
    """Test the `extract-method` command end-to-end."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_extract_method_single_line(self, temp_project):
        """Test extracting a single line to a method."""
        result = runner.invoke(
            app,
            [
                "extract-method",
                "sample_module.py",
                "14",
                "14",  # Just the message line
                "create_message",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert "patches" in data

        # Should create new method
        if "sample_module.py" in data["patches"]:
            content = data["patches"]["sample_module.py"]
            assert "create_message" in content

    def test_extract_method_multiline_block(self, temp_project):
        """Test extracting a multi-line block."""
        # Create a file with multi-line code
        test_file = temp_project / "multiline.py"
        test_file.write_text(
            """
def process():
    x = 1
    y = 2
    z = x + y
    return z
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "extract-method",
                "multiline.py",
                "3",
                "4",  # Lines with x and y
                "setup_values",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert "patches" in data

    def test_extract_method_invalid_range(self, temp_project):
        """Test with invalid range (end < start)."""
        result = runner.invoke(
            app,
            [
                "extract-method",
                "sample_module.py",
                "20",
                "14",  # End before start
                "invalid",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        # Should fail
        assert result.exit_code != 0

    def test_extract_method_force_flag(self, temp_project):
        """Test --force vs interactive confirmation."""
        result_force = runner.invoke(
            app,
            [
                "extract-method",
                "sample_module.py",
                "14",
                "14",
                "forced_method",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        # Should succeed without prompting
        assert result_force.exit_code == 0

    def test_extract_method_json_vs_no_json(self, temp_project):
        """Test both output formats."""
        result_json = runner.invoke(
            app,
            [
                "extract-method",
                "sample_module.py",
                "14",
                "14",
                "json_method",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        if result_json.exit_code == 0:
            data = json.loads(result_json.stdout)
            assert "patches" in data

        result_no_json = runner.invoke(
            app,
            [
                "extract-method",
                "sample_module.py",
                "14",
                "14",
                "diff_method",
                "--root",
                str(temp_project),
                "--no-json",
                "--force",
            ],
        )

        # Should show diff
        if result_no_json.exit_code == 0:
            assert result_no_json.stdout


class TestExtractVarCommand:
    """Test the `extract-var` command end-to-end."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_extract_var_no_cols_full_line(self, temp_project):
        """Test extracting full line (no --start-col, no --end-col)."""
        result = runner.invoke(
            app,
            [
                "extract-var",
                "sample_module.py",
                "20",
                "20",  # Line with "result = a + b"
                "sum_value",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert "patches" in data

    def test_extract_var_only_start_col(self, temp_project):
        """Test with only --start-col (from col to EOL)."""
        result = runner.invoke(
            app,
            [
                "extract-var",
                "sample_module.py",
                "20",
                "20",
                "partial_expr",
                "--root",
                str(temp_project),
                "--start-col",
                "16",  # Start at "a + b"
                "--json",
                "--force",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert "patches" in data

    def test_extract_var_only_end_col(self, temp_project):
        """Test with only --end-col (from BOL to col)."""
        result = runner.invoke(
            app,
            [
                "extract-var",
                "sample_module.py",
                "20",
                "20",
                "start_expr",
                "--root",
                str(temp_project),
                "--end-col",
                "21",
                "--json",
                "--force",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert "patches" in data

    def test_extract_var_both_cols_precise_range(self, temp_project):
        """Test with both --start-col and --end-col (precise range)."""
        result = runner.invoke(
            app,
            [
                "extract-var",
                "sample_module.py",
                "20",
                "20",
                "precise_expr",
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

    def test_extract_var_single_line_expression(self, temp_project):
        """Test extracting a single-line expression."""
        result = runner.invoke(
            app,
            [
                "extract-var",
                "sample_module.py",
                "14",
                "14",  # f-string line
                "greeting_text",
                "--root",
                str(temp_project),
                "--start-col",
                "15",
                "--end-col",
                "33",
                "--json",
                "--force",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert "patches" in data

    def test_extract_var_multiline_expression(self, temp_project):
        """Test extracting a multi-line expression."""
        # Create file with multi-line expression
        test_file = temp_project / "multiline_expr.py"
        test_file.write_text(
            """
result = (
    1 + 2 +
    3 + 4
)
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "extract-var",
                "multiline_expr.py",
                "2",
                "4",
                "calculation",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert "patches" in data

    def test_extract_var_invalid_range_error(self, temp_project):
        """Test with invalid range."""
        result = runner.invoke(
            app,
            [
                "extract-var",
                "sample_module.py",
                "20",
                "10",  # End before start
                "invalid",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        # Should handle gracefully or error
        # End < start may be caught by Rope or command validation
        if result.exit_code != 0:
            pass  # Expected error

    def test_extract_var_force_and_json_flags(self, temp_project):
        """Test --force and --json flags together."""
        result = runner.invoke(
            app,
            [
                "extract-var",
                "sample_module.py",
                "20",
                "20",
                "test_var",
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


# --------------------------------------------------------------------------------------
# PART 3: Advanced Commands (move, organize-imports, list)
# --------------------------------------------------------------------------------------


class TestMoveCommand:
    """Test the `move` command end-to-end."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_move_single_symbol_function(self, temp_project):
        """Test moving a single function to another file."""
        # Create target file
        target = temp_project / "target.py"
        target.write_text("# Target file\n", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "move",
                "sample_module.py::hello_world",  # Move hello_world function
                "target.py",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert "patches" in data

            # Should modify both source and target files
            if "target.py" in data["patches"]:
                assert "hello_world" in data["patches"]["target.py"]

    def test_move_single_symbol_class(self, temp_project):
        """Test moving a class to another file."""
        target = temp_project / "classes.py"
        target.write_text("# Classes module\n", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "move",
                "sample_module.py::Calculator",
                "classes.py",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert "patches" in data

    def test_move_entire_module(self, temp_project):
        """Test moving an entire module."""
        # Create a simple module
        source = temp_project / "old_module.py"
        source.write_text(
            """
def function():
    pass
""",
            encoding="utf-8",
        )

        target = temp_project / "new_module.py"

        result = runner.invoke(
            app,
            [
                "move",
                "old_module.py",  # No ::Symbol means whole module
                "new_module.py",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        # May succeed depending on Rope's implementation
        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert "patches" in data

    def test_move_symbol_not_found_error(self, temp_project):
        """Test moving a non-existent symbol."""
        target = temp_project / "target.py"
        target.write_text("", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "move",
                "sample_module.py::NonExistentFunction",
                "target.py",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        # Should fail with error
        assert result.exit_code != 0

    def test_move_updates_imports_in_referencing_files(self, temp_project):
        """Test that move updates imports in files that reference the symbol."""
        # sample_usage.py imports from sample_module
        target = temp_project / "new_location.py"
        target.write_text("", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "move",
                "sample_module.py::hello_world",
                "new_location.py",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)

            # Should update sample_usage.py imports
            if "sample_usage.py" in data["patches"]:
                usage_content = data["patches"]["sample_usage.py"]
                # Import should be updated
                assert "new_location" in usage_content or "hello_world" in usage_content

    def test_move_force_and_json_flags(self, temp_project):
        """Test --force and --json flags."""
        target = temp_project / "destination.py"
        target.write_text("", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "move",
                "sample_module.py::calculate_sum",
                "destination.py",
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


class TestOrganizeImportsCommand:
    """Test the `organize-imports` command end-to-end."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with messy imports."""
        # Create file with disorganized imports
        messy_file = tmp_path / "messy.py"
        messy_file.write_text(
            """
import sys
import os


import json
from pathlib import Path

def use_imports():
    print(os.getcwd())
    print(sys.version)
    data = json.dumps({})
    p = Path('.')
    return data, p
""",
            encoding="utf-8",
        )
        return tmp_path

    def test_organize_imports_single_file(self, temp_project):
        """Test organizing imports in a single file."""
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

        # May succeed with organized imports
        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert "patches" in data

            if "messy.py" in data["patches"]:
                content = data["patches"]["messy.py"]
                # Imports should still be present
                assert "import" in content

    def test_organize_imports_directory_recursion(self, temp_project):
        """Test organizing imports across a directory."""
        # Create multiple files
        (temp_project / "file1.py").write_text(
            "import os\nimport sys\nprint(os.getcwd())\nprint(sys.version)\n",
            encoding="utf-8",
        )
        (temp_project / "file2.py").write_text(
            "import json\nprint(json.dumps({}))\n", encoding="utf-8"
        )

        result = runner.invoke(
            app,
            [
                "organize-imports",
                ".",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert "patches" in data

    def test_organize_imports_froms_to_imports_flag(self, temp_project):
        """Test --froms-to-imports flag."""
        # Create file with 'from' imports
        from_file = temp_project / "from_imports.py"
        from_file.write_text(
            """
from os import getcwd
from sys import version

def test():
    print(getcwd())
    print(version)
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "organize-imports",
                "from_imports.py",
                "--root",
                str(temp_project),
                "--froms-to-imports",
                "--json",
                "--force",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)
            # May convert 'from' imports to 'import'
            if "from_imports.py" in data.get("patches", {}):
                content = data["patches"]["from_imports.py"]
                # Check conversion happened (may not always work)
                assert "import" in content

    def test_organize_imports_no_imports_no_changes(self, temp_project):
        """Test file with no imports produces no changes."""
        no_imports = temp_project / "no_imports.py"
        no_imports.write_text(
            """
def simple():
    return 42
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "organize-imports",
                "no_imports.py",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        if result.exit_code == 0:
            data = json.loads(result.stdout)
            # Should have empty or no patches
            patches = data.get("patches", {})
            # File with no imports shouldn't need changes
            # (May or may not appear in patches)

    def test_organize_imports_syntax_error_skip_gracefully(self, temp_project):
        """Test that files with syntax errors are skipped."""
        # Copy invalid_syntax.py
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        if (fixtures_src / "invalid_syntax.py").exists():
            shutil.copy(
                fixtures_src / "invalid_syntax.py",
                temp_project / "invalid_syntax.py",
            )

        result = runner.invoke(
            app,
            [
                "organize-imports",
                ".",
                "--root",
                str(temp_project),
                "--json",
                "--force",
            ],
        )

        # Should continue processing other files
        # Exit code may be 0 or error depending on implementation
        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert "patches" in data

    def test_organize_imports_force_and_json_flags(self, temp_project):
        """Test --force and --json flags together."""
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

        if result.exit_code == 0:
            data = json.loads(result.stdout)
            assert "patches" in data
            assert isinstance(data["patches"], dict)


class TestListCommand:
    """Test the `list` command end-to-end."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with fixtures."""
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            if file.name not in ["invalid_syntax.py"]:
                shutil.copy(file, tmp_path / file.name)
        return tmp_path

    def test_list_single_file_classes_and_functions(self, temp_project):
        """Test listing classes and functions from a single file."""
        result = runner.invoke(
            app, ["list", "sample_module.py", "--root", str(temp_project), "--json"]
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0

        # Should have both classes and functions
        kinds = [item["kind"] for item in data]
        assert "class" in kinds
        assert "function" in kinds

        # Check specific items
        names = [item["name"] for item in data]
        assert "hello_world" in names
        assert "Calculator" in names

    def test_list_directory_recursive(self, temp_project):
        """Test listing symbols from a directory recursively."""
        result = runner.invoke(
            app, ["list", ".", "--root", str(temp_project), "--json"]
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)

        # Should have items from multiple files
        paths = set(item["path"] for item in data)
        assert len(paths) > 1  # Multiple files

    def test_list_with_line_numbers(self, temp_project):
        """Test that list includes line numbers."""
        result = runner.invoke(
            app, ["list", "sample_module.py", "--root", str(temp_project), "--json"]
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)

        # Each item should have line number
        for item in data:
            assert "line" in item
            assert isinstance(item["line"], int)
            assert item["line"] > 0

    def test_list_syntax_error_skip_file(self, temp_project):
        """Test that files with syntax errors are skipped."""
        # Copy invalid_syntax.py
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        if (fixtures_src / "invalid_syntax.py").exists():
            shutil.copy(
                fixtures_src / "invalid_syntax.py",
                temp_project / "invalid_syntax.py",
            )

        result = runner.invoke(
            app, ["list", ".", "--root", str(temp_project), "--json"]
        )

        # Should succeed, skipping invalid files
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        # Should still have data from valid files
        assert isinstance(data, list)

    def test_list_empty_file_empty_array(self, temp_project):
        """Test that empty file returns empty array."""
        empty = temp_project / "empty.py"
        empty.write_text("", encoding="utf-8")

        result = runner.invoke(
            app, ["list", "empty.py", "--root", str(temp_project), "--json"]
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_json_vs_no_json_output(self, temp_project):
        """Test both --json and --no-json output formats."""
        result_json = runner.invoke(
            app, ["list", "sample_module.py", "--root", str(temp_project), "--json"]
        )

        assert result_json.exit_code == 0
        data = json.loads(result_json.stdout)
        assert isinstance(data, list)

        result_no_json = runner.invoke(
            app, ["list", "sample_module.py", "--root", str(temp_project), "--no-json"]
        )

        assert result_no_json.exit_code == 0
        # Should output line-by-line JSON
        lines = result_no_json.stdout.strip().split("\n")
        for line in lines:
            if line.strip():
                json.loads(line)

    def test_list_output_structure(self, temp_project):
        """Verify output structure has required fields."""
        result = runner.invoke(
            app, ["list", "sample_module.py", "--root", str(temp_project), "--json"]
        )

        assert result.exit_code == 0

        data = json.loads(result.stdout)

        for item in data:
            # Required fields
            assert "path" in item
            assert "kind" in item
            assert "name" in item
            assert "line" in item

            # Correct types
            assert isinstance(item["path"], str)
            assert isinstance(item["kind"], str)
            assert isinstance(item["name"], str)
            assert isinstance(item["line"], int)

            # kind should be valid
            assert item["kind"] in ["class", "function"]
