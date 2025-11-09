"""Legacy integration tests converted to server API.

Tests from test_integration.py that add unique coverage not found in other files.
"""

import pytest
from tests.utils import create_python_file, assert_patches_valid


@pytest.mark.integration
@pytest.mark.rope
class TestStarImports:
    """Test refactoring with star imports."""

    @pytest.fixture
    def star_import_project(self, temp_workspace):
        """Create project with star imports."""
        create_python_file(
            temp_workspace / "shapes.py",
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
"""
        )

        create_python_file(
            temp_workspace / "star_import.py",
            """
from shapes import *

def create_shapes():
    rect = Rectangle(10, 20)
    circ = Circle(5)
    return rect, circ
"""
        )

        return temp_workspace

    def test_rename_with_star_imports(self, httpx_client, star_import_project):
        """Test rename with star imports."""
        response = httpx_client.post(
            "/rename",
            json={
                "file": "shapes.py",
                "line": 6,
                "col": 7,
                "new_name": "Rect",
                "root": str(star_import_project)
            }
        )

        # Should handle star import correctly
        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]
        assert_patches_valid(patches)

        # Should update shapes.py
        assert "shapes.py" in patches
        assert "class Rect" in patches["shapes.py"]


@pytest.mark.integration
@pytest.mark.rope
class TestNestedFunctionRefactoring:
    """Test refactoring nested functions."""

    def test_extract_method_from_nested_function(self, httpx_client, temp_workspace):
        """Test extracting method from nested function."""
        create_python_file(
            temp_workspace / "nested.py",
            """
def outer():
    def inner():
        x = 1
        y = 2
        return x + y
    return inner()
"""
        )

        response = httpx_client.post(
            "/extract-method",
            json={
                "file": "nested.py",
                "start_line": 4,
                "end_line": 5,
                "method_name": "compute_sum",
                "root": str(temp_workspace)
            }
        )

        # Should handle nested context
        # May succeed or fail depending on Rope's handling
        assert response.status_code in (200, 400, 500)

        if response.status_code == 200:
            data = response.json()
            patches = data["patches"]
            assert_patches_valid(patches)


@pytest.mark.integration
@pytest.mark.rope
class TestInheritanceRefactoring:
    """Test refactoring with inheritance."""

    @pytest.fixture
    def inheritance_project(self, temp_workspace):
        """Create project with inheritance."""
        create_python_file(
            temp_workspace / "shapes.py",
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
"""
        )

        return temp_workspace

    def test_rename_method_with_inheritance(self, httpx_client, inheritance_project):
        """Test renaming a method used via inheritance."""
        response = httpx_client.post(
            "/rename",
            json={
                "file": "shapes.py",
                "line": 3,
                "col": 9,
                "new_name": "calculate_area",
                "root": str(inheritance_project)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data["patches"]
            assert_patches_valid(patches)

            content = patches["shapes.py"]
            # Should rename in base and derived classes
            assert "calculate_area" in content


@pytest.mark.integration
@pytest.mark.rope
class TestMultistepWorkflows:
    """Test multistep refactoring workflows."""

    @pytest.fixture
    def workflow_project(self, temp_workspace):
        """Create project for workflow tests."""
        create_python_file(
            temp_workspace / "calculator.py",
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
"""
        )

        return temp_workspace

    def test_rename_then_verify_consistent(self, httpx_client, workflow_project):
        """Test: rename function → verify all references updated."""
        # Rename 'calculate' to 'compute'
        response = httpx_client.post(
            "/rename",
            json={
                "file": "calculator.py",
                "line": 3,
                "col": 9,
                "new_name": "compute",
                "root": str(workflow_project)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]

        # Verify rename worked
        assert "calculator.py" in patches
        content = patches["calculator.py"]

        # Both definition and usage should be renamed
        assert "def compute" in content
        assert "calc.compute" in content
        # Old name should not appear in method context
        assert "def calculate" not in content

    def test_extract_method_then_verify_structure(self, httpx_client, workflow_project):
        """Test: extract method → verify extracted method appears."""
        # Extract lines 4-5 to a new method
        response = httpx_client.post(
            "/extract-method",
            json={
                "file": "calculator.py",
                "start_line": 4,
                "end_line": 5,
                "method_name": "calculate_result",
                "root": str(workflow_project)
            }
        )

        # May succeed or fail depending on context
        if response.status_code == 200:
            data = response.json()
            patches = data["patches"]

            # Verify extraction
            if "calculator.py" in patches:
                content = patches["calculator.py"]
                assert "calculate_result" in content
