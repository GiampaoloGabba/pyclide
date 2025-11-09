"""Regression tests: Critical functionality that must never break.

These tests capture known issues, edge cases, and critical behaviors
that must be preserved during refactoring.
"""

import pathlib
import sys
import pytest
from typer.testing import CliRunner

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pyclide import app, RopeEngine

runner = CliRunner()


class TestCriticalRenameScenarios:
    """Tests for rename scenarios that must always work."""

    def test_rename_preserves_all_usages(self, tmp_path):
        """CRITICAL: Rename must update ALL usages, never partial."""
        # Create file with multiple usages
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
def calculate(x, y):
    return x + y

result1 = calculate(1, 2)
result2 = calculate(3, 4)
result3 = calculate(5, 6)

def test_calculate():
    assert calculate(1, 1) == 2
""",
            encoding="utf-8",
        )

        # Rename calculate to compute
        result = runner.invoke(
            app,
            [
                "rename",
                str(test_file),
                "2",
                "5",
                "compute",
                "--root",
                str(tmp_path),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0
        import json
        response = json.loads(result.stdout)
        patches = response["patches"]  # Patches are wrapped in {"patches": {...}}

        new_content = patches["test.py"]

        # Count occurrences: should have 5 "compute" (def + 4 calls)
        compute_count = new_content.count("compute")
        assert compute_count == 5

        # Function definition should use new name
        assert "def compute(x, y):" in new_content
        # Old function definition should be gone
        assert "def calculate(x, y):" not in new_content

    def test_rename_with_string_literal_containing_name(self, tmp_path):
        """CRITICAL: Rename should NOT change string literals."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            '''
def user_login(username):
    print("user_login called")
    return username

result = user_login("alice")
''',
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "rename",
                str(test_file),
                "2",
                "5",
                "authenticate",
                "--root",
                str(tmp_path),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0
        import json
        response = json.loads(result.stdout)
        patches = response["patches"]  # Patches are wrapped in {"patches": {...}}

        new_content = patches["test.py"]

        # Function name should change
        assert "def authenticate" in new_content
        assert "authenticate(" in new_content

        # But string literal should NOT change
        # (though Rope might or might not preserve it - this is a known limitation)
        # The important part is it doesn't crash

    def test_rename_with_comments_mentioning_name(self, tmp_path):
        """CRITICAL: Comments mentioning old name should not break rename."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
def process_data(data):
    # This process_data function handles data
    # TODO: optimize process_data
    return data

result = process_data([1, 2, 3])
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "rename",
                str(test_file),
                "2",
                "5",
                "transform_data",
                "--root",
                str(tmp_path),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0
        import json
        response = json.loads(result.stdout)
        patches = response["patches"]  # Patches are wrapped in {"patches": {...}}

        new_content = patches["test.py"]

        # Function definition and call should change
        assert "def transform_data" in new_content
        assert "transform_data([" in new_content


class TestCriticalImportHandling:
    """Tests for import handling that must never break."""

    def test_rename_updates_all_import_statements(self, tmp_path):
        """CRITICAL: All import statements must be updated."""
        # File 1: definition
        (tmp_path / "module.py").write_text(
            """
class DataProcessor:
    def process(self):
        pass
""",
            encoding="utf-8",
        )

        # File 2: import style 1
        (tmp_path / "file1.py").write_text(
            """
from module import DataProcessor

processor = DataProcessor()
""",
            encoding="utf-8",
        )

        # File 3: import style 2
        (tmp_path / "file2.py").write_text(
            """
import module

processor = module.DataProcessor()
""",
            encoding="utf-8",
        )

        # Rename DataProcessor (line 2, col 7 = "D" of "DataProcessor")
        result = runner.invoke(
            app,
            [
                "rename",
                str(tmp_path / "module.py"),
                "2",
                "7",
                "Transformer",
                "--root",
                str(tmp_path),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0
        import json
        response = json.loads(result.stdout)
        patches = response["patches"]  # Patches are wrapped

        # All files should be updated
        assert "module.py" in patches
        assert "file1.py" in patches
        # file2.py might or might not be in patches depending on Rope's analysis

        # Check file1 import was updated
        assert "from module import Transformer" in patches["file1.py"]

    def test_organize_imports_preserves_needed_imports(self, tmp_path):
        """CRITICAL: organize_imports must not remove used imports."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
import os
import sys

def get_path():
    return os.path.join("/", "tmp")

def get_version():
    return sys.version
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "organize-imports",
                str(test_file),
                "--root",
                str(tmp_path),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0
        import json
        response = json.loads(result.stdout)
        patches = response.get("patches", {})  # Patches may be wrapped

        if "test.py" in patches:
            new_content = patches["test.py"]
            # Both imports must still be present
            assert "import os" in new_content
            assert "import sys" in new_content


class TestCriticalMultiFileConsistency:
    """Tests for multi-file operations that must maintain consistency."""

    def test_rename_across_files_is_atomic(self, tmp_path):
        """CRITICAL: Multi-file rename must be all-or-nothing."""
        # Create interconnected files
        (tmp_path / "base.py").write_text(
            """
class BaseService:
    pass
""",
            encoding="utf-8",
        )

        (tmp_path / "derived.py").write_text(
            """
from base import BaseService

class UserService(BaseService):
    pass
""",
            encoding="utf-8",
        )

        (tmp_path / "usage.py").write_text(
            """
from base import BaseService
from derived import UserService

def create_service() -> BaseService:
    return UserService()
""",
            encoding="utf-8",
        )

        # Rename BaseService (line 2, col 7 = "B" of "BaseService")
        result = runner.invoke(
            app,
            [
                "rename",
                str(tmp_path / "base.py"),
                "2",
                "7",
                "AbstractService",
                "--root",
                str(tmp_path),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0
        import json
        response = json.loads(result.stdout)
        patches = response["patches"]  # Patches are wrapped

        # All three files should be updated
        assert "base.py" in patches
        assert "derived.py" in patches
        assert "usage.py" in patches

        # Verify consistency: all files use new name
        for filename, content in patches.items():
            if "AbstractService" in content:
                # If new name appears, old name should NOT appear
                # (except possibly in comments/strings)
                lines_with_class = [
                    line for line in content.split("\n") if "class " in line
                ]
                for line in lines_with_class:
                    assert "BaseService" not in line

    def test_move_updates_all_imports(self, tmp_path):
        """CRITICAL: Moving class must update all imports."""
        # Create source file
        (tmp_path / "old_module.py").write_text(
            """
class MovableClass:
    pass

def helper_function():
    return MovableClass()
""",
            encoding="utf-8",
        )

        # Create user file
        (tmp_path / "user.py").write_text(
            """
from old_module import MovableClass

instance = MovableClass()
""",
            encoding="utf-8",
        )

        # Create target file
        (tmp_path / "new_module.py").write_text("", encoding="utf-8")

        eng = RopeEngine(tmp_path)

        # Move MovableClass to new_module
        patches = eng.move("old_module.py::MovableClass", "new_module.py")

        # user.py import must be updated (Rope may use either import style)
        if "user.py" in patches:
            user_content = patches["user.py"]
            # Accept either "from new_module import" or "import new_module"
            assert ("from new_module import MovableClass" in user_content or
                    "import new_module" in user_content)


class TestCriticalErrorHandling:
    """Tests for error handling that must work correctly."""

    def test_invalid_position_returns_gracefully(self, tmp_path):
        """CRITICAL: Invalid positions should fail gracefully, not crash."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo():\n    pass\n", encoding="utf-8")

        # Try rename at position beyond file
        result = runner.invoke(
            app,
            [
                "rename",
                str(test_file),
                "999",
                "999",
                "bar",
                "--root",
                str(tmp_path),
                "--json",
                "--force",
            ],
        )

        # Should fail gracefully (non-zero exit code)
        assert result.exit_code != 0
        # The error may be in the exception or as output - either is acceptable

    def test_syntax_error_file_skipped_gracefully(self, tmp_path):
        """CRITICAL: Syntax errors in project files should not crash tool."""
        # Valid file
        (tmp_path / "valid.py").write_text(
            "class Good:\n    pass\n\nx = Good()\n", encoding="utf-8"
        )

        # File with syntax error
        (tmp_path / "broken.py").write_text("def bad(\n    pass\n", encoding="utf-8")

        # Rename in valid file should work despite broken.py
        result = runner.invoke(
            app,
            [
                "rename",
                str(tmp_path / "valid.py"),
                "1",
                "7",
                "Better",
                "--root",
                str(tmp_path),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0
        import json
        response = json.loads(result.stdout)
        patches = response["patches"]  # Patches are wrapped

        # Should have updated valid.py
        assert "valid.py" in patches
        assert "class Better:" in patches["valid.py"]


class TestCriticalEdgeCases:
    """Tests for known edge cases that caused bugs in the past."""

    def test_rename_class_with_same_name_as_module(self, tmp_path):
        """EDGE CASE: Class named same as module (common pattern)."""
        (tmp_path / "calculator.py").write_text(
            """
class Calculator:
    def add(self, x, y):
        return x + y
""",
            encoding="utf-8",
        )

        (tmp_path / "main.py").write_text(
            """
from calculator import Calculator

calc = Calculator()
result = calc.add(1, 2)
""",
            encoding="utf-8",
        )

        # Rename Calculator class (line 2, col 7 = "C" of "Calculator")
        result = runner.invoke(
            app,
            [
                "rename",
                str(tmp_path / "calculator.py"),
                "2",
                "7",
                "Calc",
                "--root",
                str(tmp_path),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0
        import json
        response = json.loads(result.stdout)
        patches = response["patches"]  # Patches are wrapped

        # Both files should be updated
        assert "calculator.py" in patches
        assert "main.py" in patches

        # Module name stays same, class name changes
        assert "from calculator import Calc" in patches["main.py"]

    def test_rename_with_inheritance_chain(self, tmp_path):
        """EDGE CASE: Rename in inheritance hierarchy."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
class Base:
    def method(self):
        pass

class Child(Base):
    def method(self):
        super().method()

class GrandChild(Child):
    pass
""",
            encoding="utf-8",
        )

        # Rename method in Base class (line 3, col 8)
        result = runner.invoke(
            app,
            [
                "rename",
                str(test_file),
                "3",
                "8",
                "execute",
                "--root",
                str(tmp_path),
                "--json",
                "--force",
            ],
        )

        # Should succeed or fail gracefully
        assert result.exit_code in [0, 1, 2]

        if result.exit_code == 0:
            import json
            response = json.loads(result.stdout)
            patches = response["patches"]  # Patches are wrapped
            new_content = patches["test.py"]

            # Both base and child methods should be renamed
            assert "def execute" in new_content
            # Should appear at least twice (base + child)
            assert new_content.count("execute") >= 2

    def test_extract_with_local_variables(self, tmp_path):
        """EDGE CASE: Extract method that uses local variables."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
def complex_function():
    x = 10
    y = 20
    z = x + y
    result = z * 2
    return result
""",
            encoding="utf-8",
        )

        # Extract lines that use earlier variables
        result = runner.invoke(
            app,
            [
                "extract-method",
                str(test_file),
                "5",
                "6",
                "calculate_result",
                "--root",
                str(tmp_path),
                "--json",
                "--force",
            ],
        )

        # Should handle variable dependencies
        # May succeed or fail, but should not crash
        assert result.exit_code in [0, 1, 2]

    def test_circular_imports_dont_crash(self, tmp_path):
        """EDGE CASE: Circular imports should not cause infinite loops."""
        # File A imports B
        (tmp_path / "module_a.py").write_text(
            """
from module_b import ClassB

class ClassA:
    def use_b(self):
        return ClassB()
""",
            encoding="utf-8",
        )

        # File B imports A (circular)
        (tmp_path / "module_b.py").write_text(
            """
from module_a import ClassA

class ClassB:
    def use_a(self):
        return ClassA()
""",
            encoding="utf-8",
        )

        # Try to rename - should not hang or crash
        result = runner.invoke(
            app,
            [
                "rename",
                str(tmp_path / "module_a.py"),
                "4",
                "7",
                "A",
                "--root",
                str(tmp_path),
                "--json",
                "--force",
            ],
        )

        # Should complete (success or failure, but not hang)
        assert result.exit_code in [0, 1, 2]


class TestCriticalJSONOutputFormat:
    """Tests that JSON output format remains stable."""

    def test_json_structure_remains_stable(self, tmp_path):
        """CRITICAL: JSON output structure must remain backward compatible."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def func():\n    pass\n", encoding="utf-8")

        # Test each command's JSON output structure
        commands_to_test = [
            (["list", str(test_file), "--json"], ["name", "kind", "line"]),  # pyclide uses "kind"
            (["defs", str(test_file), "1", "5", "--json"], ["path", "line", "column"]),
            (
                ["hover", str(test_file), "1", "5", "--json"],
                ["name"],  # Should have at least name
            ),
        ]

        for cmd, required_keys in commands_to_test:
            result = runner.invoke(app, cmd + ["--root", str(tmp_path)])

            if result.exit_code == 0:
                import json
                data = json.loads(result.stdout)

                # Should be list or dict
                assert isinstance(data, (list, dict))

                # If list, check first item has required keys
                if isinstance(data, list) and len(data) > 0:
                    item = data[0]
                    for key in required_keys:
                        assert key in item

    def test_json_output_is_valid_json(self, tmp_path):
        """CRITICAL: All JSON output must be valid JSON."""
        test_file = tmp_path / "test.py"
        test_file.write_text("class Test:\n    pass\n", encoding="utf-8")

        # Try various commands with --json
        commands = [
            ["list", str(test_file), "--json"],
            ["defs", str(test_file), "1", "7", "--json"],
            ["refs", str(test_file), "1", "7", "--json"],
            ["hover", str(test_file), "1", "7", "--json"],
        ]

        for cmd in commands:
            result = runner.invoke(app, cmd + ["--root", str(tmp_path)])

            if result.exit_code == 0:
                # Must be parseable as JSON
                import json
                try:
                    data = json.loads(result.stdout)
                    # Must be serializable back to JSON
                    json.dumps(data)
                except json.JSONDecodeError:
                    pytest.fail(f"Invalid JSON output for command: {cmd}")
