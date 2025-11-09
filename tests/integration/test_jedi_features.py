"""Tests for Jedi-based features (goto, infer, refs, hover)."""

import json
import pathlib

import pytest

from tests.utils import assert_locations_response, get_relative_path


@pytest.mark.jedi
class TestJediFeatures:
    """Test Jedi integration features via server API."""

    def test_jedi_goto_function_definition(self, httpx_client, temp_workspace):
        """Test goto for function definition via /defs endpoint."""
        # In sample_usage.py, line 9 has "hello_world" - should go to its definition
        response = httpx_client.post(
            "/defs",
            json={
                "file": "sample_usage.py",
                "line": 9,
                "col": 20,  # on "hello_world" in the function call
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert_locations_response(data, min_count=1)

        # Jedi may point to the import statement in sample_usage.py or the definition in sample_module.py
        # Both are valid behaviors
        locations = data["locations"]
        assert len(locations) > 0
        assert "sample_usage.py" in locations[0]["file"] or "sample_module.py" in locations[0]["file"]

    def test_jedi_goto_class_definition(self, httpx_client, temp_workspace):
        """Test goto for class definition via /defs endpoint."""
        # Line 13, column 15 is on "Calculator" in the class instantiation
        response = httpx_client.post(
            "/defs",
            json={
                "file": "sample_usage.py",
                "line": 13,
                "col": 15,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert_locations_response(data, min_count=1)

        # Jedi may point to the import statement or the class definition
        locations = data["locations"]
        assert "sample_usage.py" in locations[0]["file"] or "sample_module.py" in locations[0]["file"]

    def test_jedi_get_references(self, httpx_client, temp_workspace):
        """Test finding references to a function via /refs endpoint."""
        # Line 4, column 5 is on the "hello_world" function definition
        response = httpx_client.post(
            "/refs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert_locations_response(data, min_count=2)  # At least definition + 1 usage

        # Should include both definition and usage
        locations = data["locations"]
        paths = [loc["file"] for loc in locations]
        assert any("sample_module.py" in p for p in paths)
        assert any("sample_usage.py" in p for p in paths)

    def test_jedi_hover_function(self, httpx_client, temp_workspace):
        """Test hover information for a function via /hover endpoint."""
        # Line 4, column 5 is on "hello_world"
        response = httpx_client.post(
            "/hover",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Check basic properties
        assert data["name"] == "hello_world"
        assert data["type"] == "function"

        # Check docstring is available
        assert data["docstring"] is not None
        assert "greeting message" in data["docstring"].lower()

    def test_jedi_hover_class_method(self, httpx_client, temp_workspace):
        """Test hover information for a class method via /hover endpoint."""
        # Line 30, column 9 is on "add" method
        response = httpx_client.post(
            "/hover",
            json={
                "file": "sample_module.py",
                "line": 30,
                "col": 9,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "add"
        assert data["type"] == "function"

        # Check signature is available (either in signature field or docstring)
        assert data["signature"] is not None or (
            data["docstring"] is not None and "add" in data["docstring"]
        )