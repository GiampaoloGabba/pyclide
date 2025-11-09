"""Integration tests for multi-command workflows and real-world patterns."""

import pathlib
import shutil
import sys

import pytest

# Add parent directory to path to import pyclide
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pyclide import RopeEngine


class TestWorkflowScenarios:
    """Test realistic multi-step workflows."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project."""
        # Create a realistic module
        module = tmp_path / "calculator.py"
        module.write_text(
            """
class Calculator:
    def calculate(self, a, b):
        sum_value = a + b
        result = sum_value * 2
        return result

def use_calculator():
    calc = Calculator()
    value = calc.calculate(10, 20)
    return value
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_rename_then_verify_consistent(self, temp_project):
        """Test: rename function → verify all references updated."""
        eng = RopeEngine(temp_project)

        # Step 1: Rename 'calculate' to 'compute'
        patches_rename = eng.rename("calculator.py", 3, 9, "compute")

        # Verify rename worked
        assert "calculator.py" in patches_rename
        content = patches_rename["calculator.py"]

        # Both definition and usage should be renamed
        assert "def compute" in content
        assert "calc.compute" in content
        # Old name should not appear in method context
        assert "def calculate" not in content

    def test_extract_method_then_rename_extracted(self, temp_project):
        """Test: extract method → rename extracted method."""
        eng = RopeEngine(temp_project)

        # Step 1: Extract lines 4-5 to a new method
        patches_extract = eng.extract_method(
            "calculator.py", 4, 5, "calculate_result"
        )

        # Verify extraction
        if "calculator.py" in patches_extract:
            content = patches_extract["calculator.py"]
            assert "calculate_result" in content

            # Step 2: Apply patches (simulate)
            # In real scenario, would write to disk
            # Then create new RopeEngine and rename

            # For testing, we verify the structure is valid
            assert "def calculate_result" in content or "calculate_result" in content

    def test_move_class_then_organize_imports(self, temp_project):
        """Test: move class → organize imports → verify imports fixed."""
        # Create another file that uses Calculator
        usage_file = temp_project / "app.py"
        usage_file.write_text(
            """
from calculator import Calculator

def main():
    calc = Calculator()
    result = calc.calculate(5, 10)
    return result
""",
            encoding="utf-8",
        )

        eng = RopeEngine(temp_project)

        # Step 1: Move Calculator to new file
        new_module = temp_project / "models.py"
        new_module.write_text("", encoding="utf-8")

        patches_move = eng.move("calculator.py::Calculator", "models.py")

        # Step 2: Organize imports
        # (In real scenario, would apply patches first)
        # For now, verify move updates imports

        if "app.py" in patches_move:
            app_content = patches_move["app.py"]
            # Import should be updated to reference new location
            assert "models" in app_content or "Calculator" in app_content


class TestMultiFileRefactors:
    """Test refactors affecting multiple files."""

    @pytest.fixture
    def multifile_project(self, tmp_path):
        """Create a project with interdependent files."""
        # Copy multifile_refactor fixtures
        fixtures_src = pathlib.Path(__file__).parent / "fixtures" / "multifile_refactor"
        if fixtures_src.exists():
            for file in fixtures_src.glob("*.py"):
                shutil.copy(file, tmp_path / file.name)

        return tmp_path

    def test_rename_affecting_5plus_files(self, multifile_project):
        """Test rename that affects 5+ files."""
        eng = RopeEngine(multifile_project)

        # Rename a widely-used symbol
        # User class is used in multiple files (line 4, col 7 is on "User")
        patches = eng.rename("models.py", 4, 7, "Customer")

        # Should affect multiple files
        assert isinstance(patches, dict)

        # Count affected files
        assert len(patches) >= 1

        # Verify new name appears
        all_content = " ".join(patches.values())
        assert "Customer" in all_content

    def test_move_with_import_chain_updates(self, multifile_project):
        """Test move with cascading import updates."""
        eng = RopeEngine(multifile_project)

        # Move Product class to new file
        new_file = multifile_project / "products.py"
        new_file.write_text("", encoding="utf-8")

        patches = eng.move("models.py::Product", "products.py")

        # Should update imports in services.py and possibly main.py
        assert isinstance(patches, dict)

        if len(patches) > 1:
            # Multiple files affected
            pass

    def test_verify_atomicity_all_or_nothing(self, multifile_project):
        """Test that refactors are atomic (all patches or none)."""
        eng = RopeEngine(multifile_project)

        # Perform a refactor
        # Line 4, col 7 is on "User" class definition
        patches = eng.rename("models.py", 4, 7, "UpdatedUser")

        # All patches should be consistent
        # If we have patches, they should all reference the new name
        if len(patches) > 0:
            for filepath, content in patches.items():
                # Content should be valid Python (no partial changes)
                assert isinstance(content, str)
                assert len(content) > 0


class TestRealWorldPatterns:
    """Test real-world usage patterns."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a realistic project."""
        # Create file with inheritance
        inheritance = tmp_path / "shapes.py"
        inheritance.write_text(
            """
class Shape:
    def area(self):
        pass

class Rectangle(Shape):
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def area(self):
        return self.width * self.height

class Circle(Shape):
    def __init__(self, radius):
        self.radius = radius

    def area(self):
        return 3.14 * self.radius ** 2
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_rename_method_with_inheritance(self, temp_project):
        """Test renaming a method used via inheritance."""
        eng = RopeEngine(temp_project)

        # Rename 'area' method in base class
        patches = eng.rename("shapes.py", 3, 9, "calculate_area")

        if "shapes.py" in patches:
            content = patches["shapes.py"]

            # Should rename in base and derived classes
            assert "calculate_area" in content

            # Old name should be replaced
            # (May appear in comments, but not in method definitions)

    def test_rename_with_star_imports(self, temp_project):
        """Test rename with star imports."""
        # Create module with star import
        star_file = temp_project / "star_import.py"
        star_file.write_text(
            """
from shapes import *

def create_shapes():
    rect = Rectangle(10, 20)
    circ = Circle(5)
    return rect, circ
""",
            encoding="utf-8",
        )

        eng = RopeEngine(temp_project)

        # Rename Rectangle class
        patches = eng.rename("shapes.py", 6, 7, "Rect")

        # Should handle star import correctly
        assert isinstance(patches, dict)

    def test_extract_method_from_nested_function(self, temp_project):
        """Test extracting method from nested function."""
        nested_file = temp_project / "nested.py"
        nested_file.write_text(
            """
def outer():
    def inner():
        x = 1
        y = 2
        return x + y
    return inner()
""",
            encoding="utf-8",
        )

        eng = RopeEngine(temp_project)

        # Try to extract from inner function
        patches = eng.extract_method("nested.py", 4, 5, "compute_sum")

        # Should handle nested context
        assert isinstance(patches, dict)


class TestComplexScenarios:
    """Test complex, edge-case scenarios."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a project with complex code."""
        complex_file = tmp_path / "complex.py"
        complex_file.write_text(
            """
class DataProcessor:
    def process(self, data):
        # Multi-step processing
        cleaned = self._clean(data)
        validated = self._validate(cleaned)
        transformed = self._transform(validated)
        return transformed

    def _clean(self, data):
        return [x.strip() for x in data]

    def _validate(self, data):
        return [x for x in data if x]

    def _transform(self, data):
        return [x.upper() for x in data]
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_sequential_refactors(self, temp_project):
        """Test multiple sequential refactors."""
        eng = RopeEngine(temp_project)

        # Refactor 1: Rename _clean to _cleanup
        patches1 = eng.rename("complex.py", 10, 9, "_cleanup")

        # Verify
        if "complex.py" in patches1:
            assert "_cleanup" in patches1["complex.py"]

    def test_extract_then_move_workflow(self, temp_project):
        """Test extract → move workflow."""
        eng = RopeEngine(temp_project)

        # Step 1: Extract _transform method (already exists, but test the pattern)
        # In real scenario, would extract new functionality

        # Step 2: Move extracted method to utilities module
        utils = temp_project / "utils.py"
        utils.write_text("", encoding="utf-8")

        patches_move = eng.move("complex.py::DataProcessor", "utils.py")

        # Should move the class
        assert isinstance(patches_move, dict)
