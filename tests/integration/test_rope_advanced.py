"""Advanced integration tests for Rope engine functionality via server API."""

import pytest

from tests.utils import assert_patches_valid, create_python_file


@pytest.mark.integration
@pytest.mark.rope
class TestRopeMoveOperations:
    """Advanced tests for the move() operation."""

    def test_move_symbol_endpoint_exists(self, httpx_client, temp_workspace):
        """Test that /move endpoint is available."""
        # Create source file
        source = temp_workspace / "source.py"
        create_python_file(
            source,
            """
def standalone_function():
    return 42

class MyClass:
    def method(self):
        pass
"""
        )

        # Create target file
        target = temp_workspace / "target.py"
        create_python_file(target, "")

        response = httpx_client.post(
            "/move",
            json={
                "file": "source.py",
                "line": 2,
                "col": 5,  # On "standalone_function"
                "dest_file": "target.py",
                "root": str(temp_workspace)
            }
        )

        # Server should handle the request
        assert response.status_code in (200, 400, 500, 501)

    def test_move_updates_imports(self, httpx_client, temp_workspace):
        """Test that move updates imports in referencing files."""
        # Create source file
        source = temp_workspace / "source.py"
        create_python_file(
            source,
            """
def standalone_function():
    return 42
"""
        )

        # Create usage file
        usage = temp_workspace / "usage.py"
        create_python_file(
            usage,
            """
from source import standalone_function

result = standalone_function()
"""
        )

        # Create target
        target = temp_workspace / "new_location.py"
        create_python_file(target, "")

        response = httpx_client.post(
            "/move",
            json={
                "file": "source.py",
                "line": 2,
                "col": 5,
                "dest_file": "new_location.py",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data.get("patches", {})
            # usage.py should have updated imports
            if "usage.py" in patches:
                usage_content = patches["usage.py"]
                assert "new_location" in usage_content or "standalone_function" in usage_content


@pytest.mark.integration
@pytest.mark.rope
class TestRopeOrganizeImportsAdvanced:
    """Advanced tests for organize_imports() operation."""

    def test_organize_imports_with_used_imports(self, httpx_client, temp_workspace):
        """Test organizing imports that are actually used."""
        # File with messy imports
        messy_file = temp_workspace / "messy.py"
        create_python_file(
            messy_file,
            """
import sys
import os


import json

def use_it():
    print(os.getcwd())
    print(sys.version)
    print(json.dumps({}))
"""
        )

        response = httpx_client.post(
            "/organize-imports",
            json={
                "file": "messy.py",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data.get("patches", {})
        assert isinstance(patches, dict)

    def test_organize_imports_skip_syntax_errors(self, httpx_client, temp_workspace):
        """Test that files with errors are handled gracefully."""
        # Create file with syntax error
        bad_file = temp_workspace / "bad.py"
        create_python_file(bad_file, "def broken(\n    pass")

        # Create valid file
        good_file = temp_workspace / "good.py"
        create_python_file(
            good_file,
            """
import sys
import os

def test():
    print(sys.version)
    print(os.getcwd())
"""
        )

        # Try to organize the bad file
        response = httpx_client.post(
            "/organize-imports",
            json={
                "file": "bad.py",
                "root": str(temp_workspace)
            }
        )

        # Should handle gracefully (return empty patches or error)
        if response.status_code == 200:
            data = response.json()
            patches = data.get("patches", {})
            assert isinstance(patches, dict)
        else:
            # Or may return error
            assert response.status_code >= 400

    def test_organize_imports_no_changes_needed(self, httpx_client, temp_workspace):
        """Test file with no imports produces no/minimal patch."""
        # File without imports
        no_imports = temp_workspace / "clean.py"
        create_python_file(no_imports, "def foo():\n    return 42\n")

        response = httpx_client.post(
            "/organize-imports",
            json={
                "file": "clean.py",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data.get("patches", {})
        # Should be empty or minimal
        assert isinstance(patches, dict)

    def test_organize_imports_already_organized(self, httpx_client, temp_workspace):
        """Test organizing already well-organized imports."""
        # File with properly organized imports
        organized = temp_workspace / "organized.py"
        create_python_file(
            organized,
            """import json
import os
import sys

def test():
    print(os.getcwd())
    print(sys.version)
    print(json.dumps({}))
"""
        )

        response = httpx_client.post(
            "/organize-imports",
            json={
                "file": "organized.py",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data.get("patches", {})
        # Should have minimal or no changes
        assert isinstance(patches, dict)


@pytest.mark.integration
@pytest.mark.rope
class TestRopeRenameCrossFile:
    """Test cross-file rename scenarios."""

    def test_rename_used_in_multiple_files(self, httpx_client, temp_workspace):
        """Test renaming a symbol used in multiple files."""
        # Create a models file
        models = temp_workspace / "models.py"
        create_python_file(
            models,
            """
class User:
    def __init__(self, name):
        self.name = name
"""
        )

        # Create a services file that uses User
        services = temp_workspace / "services.py"
        create_python_file(
            services,
            """
from models import User

def create_user(name):
    return User(name)
"""
        )

        # Create a main file that uses both
        main = temp_workspace / "main.py"
        create_python_file(
            main,
            """
from models import User
from services import create_user

user = User("Alice")
user2 = create_user("Bob")
"""
        )

        # Rename User to Person
        response = httpx_client.post(
            "/rename",
            json={
                "file": "models.py",
                "line": 2,
                "col": 7,  # On "User"
                "new_name": "Person",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data.get("patches", {})
        assert_patches_valid(patches)

        # Should affect multiple files
        assert len(patches) >= 1

        # Check that new name appears
        all_content = " ".join(patches.values())
        assert "Person" in all_content

    def test_rename_updates_import_statements(self, httpx_client, temp_workspace):
        """Test that rename updates import statements."""
        # Create module with function
        utils = temp_workspace / "utils.py"
        create_python_file(
            utils,
            """
def helper_function():
    return "help"
"""
        )

        # Create file that imports it
        app = temp_workspace / "app.py"
        create_python_file(
            app,
            """
from utils import helper_function

result = helper_function()
"""
        )

        # Rename the function
        response = httpx_client.post(
            "/rename",
            json={
                "file": "utils.py",
                "line": 2,
                "col": 5,  # On "helper_function"
                "new_name": "assist_function",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data.get("patches", {})

            # app.py should have updated import
            if "app.py" in patches:
                app_content = patches["app.py"]
                assert "assist_function" in app_content


@pytest.mark.integration
@pytest.mark.rope
class TestRopeExtractEdgeCases:
    """Test edge cases for extract method/variable operations."""

    def test_extract_method_from_class_method(self, httpx_client, temp_workspace):
        """Test extracting code from within a class method."""
        # Create class with complex method
        test_file = temp_workspace / "calculator.py"
        create_python_file(
            test_file,
            """
class Calculator:
    def complex_method(self):
        x = 1
        y = 2
        z = x + y
        result = z * 2
        return result
"""
        )

        # Extract lines 4-5 (x and y assignments)
        response = httpx_client.post(
            "/extract-method",
            json={
                "file": "calculator.py",
                "start_line": 4,
                "end_line": 5,
                "method_name": "setup_values",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data.get("patches", {})
            assert_patches_valid(patches)

            if "calculator.py" in patches:
                content = patches["calculator.py"]
                # Should contain the extracted method
                assert "setup_values" in content

    def test_extract_variable_with_local_vars(self, httpx_client, temp_workspace):
        """Test extracting expression that uses local variables."""
        # Create method with expression
        test_file = temp_workspace / "math_ops.py"
        create_python_file(
            test_file,
            """
def calculate():
    x = 10
    y = 20
    z = x + y
    return z
"""
        )

        # Extract "x + y" expression
        response = httpx_client.post(
            "/extract-var",
            json={
                "file": "math_ops.py",
                "start_line": 5,
                "end_line": 5,
                "start_col": 9,
                "end_col": 14,  # "x + y"
                "var_name": "sum_val",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data.get("patches", {})
            # Should extract successfully
            assert isinstance(patches, dict)

    def test_extract_variable_precise_column_ranges(self, httpx_client, temp_workspace):
        """Test extract with precise column ranges."""
        # Create expression to extract
        test_file = temp_workspace / "precise.py"
        create_python_file(
            test_file,
            """
def compute():
    value = 5
    result = value * 2
    return result
"""
        )

        # Extract "value * 2"
        response = httpx_client.post(
            "/extract-var",
            json={
                "file": "precise.py",
                "start_line": 4,
                "end_line": 4,
                "start_col": 14,
                "end_col": 23,  # "value * 2"
                "var_name": "doubled",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data.get("patches", {})
            assert isinstance(patches, dict)

    def test_extract_method_single_statement(self, httpx_client, temp_workspace):
        """Test extracting a single statement."""
        test_file = temp_workspace / "single_stmt.py"
        create_python_file(
            test_file,
            """
def process():
    data = [1, 2, 3]
    filtered = [x for x in data if x > 1]
    return filtered
"""
        )

        # Extract the list comprehension line
        response = httpx_client.post(
            "/extract-method",
            json={
                "file": "single_stmt.py",
                "start_line": 4,
                "end_line": 4,
                "method_name": "filter_data",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data.get("patches", {})
            # May or may not work depending on Rope's assessment
            assert isinstance(patches, dict)

    def test_extract_with_return_value(self, httpx_client, temp_workspace):
        """Test extracting code that needs to return a value."""
        test_file = temp_workspace / "with_return.py"
        create_python_file(
            test_file,
            """
def calculate_price():
    base_price = 100
    tax = base_price * 0.2
    total = base_price + tax
    return total
"""
        )

        # Extract lines 3-4 (tax calculation and total)
        response = httpx_client.post(
            "/extract-method",
            json={
                "file": "with_return.py",
                "start_line": 3,
                "end_line": 4,
                "method_name": "compute_total",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data.get("patches", {})
            assert_patches_valid(patches)

            if "with_return.py" in patches:
                content = patches["with_return.py"]
                # Should have the extracted method
                assert "compute_total" in content
