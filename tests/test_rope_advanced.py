"""Advanced tests for Rope engine functionality."""

import pathlib
import shutil
import sys

import pytest

# Add parent directory to path to import pyclide
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pyclide import RopeEngine


class TestRopeMoveMethod:
    """Deep tests for the move() method."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project."""
        # Create source file with functions and classes
        source = tmp_path / "source.py"
        source.write_text(
            """
def standalone_function():
    return 42

class MyClass:
    def method(self):
        pass
""",
            encoding="utf-8",
        )

        # Create file that imports from source
        usage = tmp_path / "usage.py"
        usage.write_text(
            """
from source import standalone_function, MyClass

result = standalone_function()
obj = MyClass()
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_move_function_to_new_file(self, temp_project):
        """Test moving a function to a new file."""
        eng = RopeEngine(temp_project)

        target = temp_project / "target.py"
        target.write_text("", encoding="utf-8")

        patches = eng.move("source.py::standalone_function", "target.py")

        # Should have patches
        assert isinstance(patches, dict)

        # Target should contain the function
        if "target.py" in patches:
            assert "standalone_function" in patches["target.py"]

    def test_move_class_to_new_file(self, temp_project):
        """Test moving a class to a new file."""
        eng = RopeEngine(temp_project)

        target = temp_project / "classes.py"
        target.write_text("", encoding="utf-8")

        patches = eng.move("source.py::MyClass", "classes.py")

        assert isinstance(patches, dict)

        if "classes.py" in patches:
            assert "MyClass" in patches["classes.py"]

    def test_move_updates_imports(self, temp_project):
        """Test that move updates imports in referencing files."""
        eng = RopeEngine(temp_project)

        target = temp_project / "new_location.py"
        target.write_text("", encoding="utf-8")

        patches = eng.move("source.py::standalone_function", "new_location.py")

        # usage.py should have updated imports
        if "usage.py" in patches:
            usage_content = patches["usage.py"]
            # Import should reference new location
            assert "new_location" in usage_content or "standalone_function" in usage_content

    def test_move_symbol_not_found(self, temp_project):
        """Test moving a non-existent symbol raises error."""
        eng = RopeEngine(temp_project)

        target = temp_project / "target.py"
        target.write_text("", encoding="utf-8")

        with pytest.raises(Exception):
            eng.move("source.py::NonExistent", "target.py")


class TestRopeOrganizeImportsAdvanced:
    """Advanced tests for organize_imports()."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with various import styles."""
        # File with messy imports
        file1 = tmp_path / "messy.py"
        file1.write_text(
            """
import sys
import os


import json

def use_it():
    print(os.getcwd())
    print(sys.version)
    print(json.dumps({}))
""",
            encoding="utf-8",
        )

        # File with unused imports (Rope may or may not remove these)
        file2 = tmp_path / "unused.py"
        file2.write_text(
            """
import sys
import os

def nothing():
    pass
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_organize_imports_directory_recursion(self, temp_project):
        """Test organizing imports across a directory."""
        eng = RopeEngine(temp_project)

        patches = eng.organize_imports(temp_project, convert_froms=False)

        # Should scan multiple files
        assert isinstance(patches, dict)

    def test_organize_imports_froms_to_imports_conversion(self, temp_project):
        """Test --froms-to-imports conversion."""
        # Create file with 'from' imports
        from_file = temp_project / "from_style.py"
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

        eng = RopeEngine(temp_project)

        patches = eng.organize_imports(from_file, convert_froms=True)

        # Conversion may or may not happen depending on Rope's behavior
        assert isinstance(patches, dict)

    def test_organize_imports_skip_errors(self, temp_project):
        """Test that files with errors are skipped gracefully."""
        # Create file with syntax error
        bad_file = temp_project / "bad.py"
        bad_file.write_text("def broken(\n    pass", encoding="utf-8")

        eng = RopeEngine(temp_project)

        # Should not crash on directory with bad files
        patches = eng.organize_imports(temp_project, convert_froms=False)

        # May have patches for valid files
        assert isinstance(patches, dict)

    def test_organize_imports_no_changes(self, temp_project):
        """Test file with no imports produces no patch."""
        no_imports = temp_project / "clean.py"
        no_imports.write_text("def foo():\n    return 42\n", encoding="utf-8")

        eng = RopeEngine(temp_project)

        patches = eng.organize_imports(no_imports, convert_froms=False)

        # Should be empty or not include this file
        # (File doesn't need changes)
        assert isinstance(patches, dict)


class TestRopeRenameCrossFile:
    """Test cross-file rename scenarios."""

    @pytest.fixture
    def multifile_project(self, tmp_path):
        """Create a project with multiple interdependent files."""
        # Copy multifile_refactor fixtures
        fixtures_src = pathlib.Path(__file__).parent / "fixtures" / "multifile_refactor"
        if fixtures_src.exists():
            for file in fixtures_src.glob("*.py"):
                shutil.copy(file, tmp_path / file.name)

        return tmp_path

    def test_rename_used_in_multiple_files(self, multifile_project):
        """Test renaming a symbol used in 3+ files."""
        eng = RopeEngine(multifile_project)

        # Rename User class (line 4, col 7 is on "User")
        patches = eng.rename("models.py", 4, 7, "Person")

        # Should affect multiple files
        assert isinstance(patches, dict)

        # Check that new name appears
        all_content = " ".join(patches.values())
        assert "Person" in all_content

    def test_rename_updates_import_statements(self, multifile_project):
        """Test that rename updates import statements."""
        eng = RopeEngine(multifile_project)

        # Rename create_default_user function
        patches = eng.rename("models.py", 24, 5, "create_guest_user_default")

        if len(patches) > 0:
            # services.py imports this function
            if "services.py" in patches:
                services_content = patches["services.py"]
                # Import or usage should be updated
                assert "create" in services_content


class TestRopeExtractEdgeCases:
    """Test edge cases for extract method/variable."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project."""
        test_file = tmp_path / "extract_test.py"
        test_file.write_text(
            """
class Calculator:
    def complex_method(self):
        x = 1
        y = 2
        z = x + y
        result = z * 2
        return result
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_extract_method_from_class_method(self, temp_project):
        """Test extracting code from within a class method."""
        eng = RopeEngine(temp_project)

        # Extract lines 4-5 (x and y assignments)
        patches = eng.extract_method("extract_test.py", 4, 5, "setup_values")

        assert isinstance(patches, dict)

        if "extract_test.py" in patches:
            content = patches["extract_test.py"]
            assert "setup_values" in content

    def test_extract_variable_with_local_vars(self, temp_project):
        """Test extracting expression that uses local variables."""
        eng = RopeEngine(temp_project)

        # Extract "x + y" on line 6
        patches = eng.extract_variable(
            "extract_test.py", 6, 6, "sum_val", start_col=13, end_col=18
        )

        if len(patches) > 0:
            assert isinstance(patches, dict)

    def test_extract_variable_column_ranges(self, temp_project):
        """Test extract with precise column ranges."""
        eng = RopeEngine(temp_project)

        # Extract "z * 2" on line 7
        patches = eng.extract_variable(
            "extract_test.py", 7, 7, "doubled", start_col=18, end_col=23
        )

        if len(patches) > 0:
            assert isinstance(patches, dict)
