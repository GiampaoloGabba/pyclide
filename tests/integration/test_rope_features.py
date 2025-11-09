"""Tests for Rope-based features (rename, occurrences, extract methods/variables)."""

import pathlib

import pytest

from tests.utils import assert_locations_response, assert_patches_valid, create_python_file


@pytest.mark.rope
class TestRopeFeatures:
    """Test Rope integration features via server API."""

    def test_rope_occurrences_function(self, httpx_client, temp_workspace):
        """Test finding occurrences of a function name via /occurrences endpoint."""
        # Find occurrences of "hello_world" function
        # Line 4, column 5 is on the function definition
        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert_locations_response(data, min_count=1)

        # Check structure of results
        locations = data["locations"]
        for loc in locations:
            assert loc["line"] > 0
            assert loc["column"] > 0

    def test_rope_occurrences_variable(self, httpx_client, temp_workspace):
        """Test finding occurrences of a variable via /occurrences endpoint."""
        # Find occurrences of "message" variable in hello_world function
        # Line 14, column 5 is on the message variable
        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "sample_module.py",
                "line": 14,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert_locations_response(data, min_count=2)  # definition + usage

    def test_rope_occurrences_class(self, httpx_client, temp_workspace):
        """Test finding occurrences of a class name via /occurrences endpoint."""
        # Find occurrences of Calculator class
        # Line 24, column 7 is on the class definition
        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "sample_module.py",
                "line": 24,
                "col": 7,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert_locations_response(data, min_count=2)  # definition + usages

    def test_rope_rename_variable(self, httpx_client, temp_workspace):
        """Test renaming a local variable via /rename endpoint."""
        # Rename "message" to "greeting_msg" in hello_world function
        # Line 14, column 5 is on the message variable
        response = httpx_client.post(
            "/rename",
            json={
                "file": "sample_module.py",
                "line": 14,
                "col": 5,
                "new_name": "greeting_msg",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "patches" in data

        patches = data["patches"]
        assert_patches_valid(patches)
        assert len(patches) > 0

        # Check that the new content contains the new name
        # The key might be relative or absolute path
        sample_module_content = None
        for file_path, content in patches.items():
            if "sample_module.py" in file_path:
                sample_module_content = content
                break

        assert sample_module_content is not None
        assert "greeting_msg" in sample_module_content
        assert 'greeting_msg = f"Hello, {name}!"' in sample_module_content
        assert "return greeting_msg" in sample_module_content

    def test_rope_rename_function(self, httpx_client, temp_workspace):
        """Test renaming a function across multiple files via /rename endpoint."""
        # Rename hello_world to greet_user
        response = httpx_client.post(
            "/rename",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "new_name": "greet_user",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]
        assert_patches_valid(patches)

        # Should change both definition and usage files
        assert len(patches) >= 1

        # Check for changes in relevant files
        has_sample_module = any("sample_module.py" in path for path in patches.keys())
        if has_sample_module:
            sample_module_content = next(
                content for path, content in patches.items() if "sample_module.py" in path
            )
            assert "def greet_user" in sample_module_content

    def test_rope_rename_class(self, httpx_client, temp_workspace):
        """Test renaming a class via /rename endpoint."""
        # Rename Calculator to MathCalculator
        response = httpx_client.post(
            "/rename",
            json={
                "file": "sample_module.py",
                "line": 24,
                "col": 7,
                "new_name": "MathCalculator",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]
        assert_patches_valid(patches)

        # Check that class definition is renamed
        sample_module_content = next(
            content for path, content in patches.items() if "sample_module.py" in path
        )
        assert "class MathCalculator:" in sample_module_content

    def test_rope_extract_variable(self, httpx_client, temp_workspace):
        """Test extracting an expression to a variable via /extract-var endpoint."""
        # Extract "a + b" in calculate_sum function
        # Line 20 has "    result = a + b"
        # Column 16 is 'a', column 21 is after 'b'
        response = httpx_client.post(
            "/extract-var",
            json={
                "file": "sample_module.py",
                "start_line": 20,
                "end_line": 20,
                "start_col": 16,
                "end_col": 21,
                "var_name": "temp_sum",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]
        assert_patches_valid(patches)

        # Should have the new variable
        sample_module_content = next(
            content for path, content in patches.items() if "sample_module.py" in path
        )
        assert "temp_sum" in sample_module_content

    def test_rope_extract_method(self, httpx_client, temp_workspace):
        """Test extracting code to a new method via /extract-method endpoint."""
        # Extract lines in hello_world that create the message
        # Line 14 to 14 (just the message creation line)
        response = httpx_client.post(
            "/extract-method",
            json={
                "file": "sample_module.py",
                "start_line": 14,
                "end_line": 14,
                "method_name": "create_greeting",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]
        assert_patches_valid(patches)

        # Should have a new function called create_greeting
        sample_module_content = next(
            content for path, content in patches.items() if "sample_module.py" in path
        )
        assert "def create_greeting" in sample_module_content or "create_greeting" in sample_module_content

    def test_rope_organize_imports(self, httpx_client, temp_workspace):
        """Test organizing imports in a file via /organize-imports endpoint."""
        # Create a test file with messy imports that ARE USED
        test_file = temp_workspace / "messy_imports.py"
        create_python_file(
            test_file,
            """
import os
import sys


import json
from pathlib import Path

def test():
    # Use the imports so they don't get removed
    print(os.path.join('a', 'b'))
    print(sys.version)
    data = json.dumps({})
    p = Path('.')
    return data, p
"""
        )

        response = httpx_client.post(
            "/organize-imports",
            json={
                "file": "messy_imports.py",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()

        # If there are changes, check they're organized
        if "patches" in data and len(data["patches"]) > 0:
            patches = data["patches"]
            messy_imports_content = next(
                (content for path, content in patches.items() if "messy_imports.py" in path),
                None
            )

            if messy_imports_content:
                # Imports should be organized and present
                assert "import" in messy_imports_content
                # Should contain the used imports
                assert "os" in messy_imports_content or "json" in messy_imports_content
