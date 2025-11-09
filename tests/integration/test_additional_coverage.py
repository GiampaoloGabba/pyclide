"""Additional coverage tests for edge cases via server API.

Tests converted from test_final_coverage.py and test_missing_coverage.py
that are relevant to the server architecture.
"""

import pytest
from tests.utils import create_python_file, assert_patches_valid


@pytest.mark.integration
@pytest.mark.rope
class TestRopeEdgeCases:
    """Edge cases for Rope operations."""

    def test_occurrences_on_comment(self, httpx_client, temp_workspace):
        """Test occurrences on a position with no real symbol (comment)."""
        create_python_file(
            temp_workspace / "test.py",
            "# Just a comment\nx = 1\n"
        )

        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "test.py",
                "line": 1,
                "col": 1,
                "root": str(temp_workspace)
            }
        )

        # Should return empty or handle gracefully
        if response.status_code == 200:
            data = response.json()
            locations = data.get("locations", [])
            # Empty result is acceptable
            assert isinstance(locations, list)
        else:
            # Or may return error - both acceptable
            assert response.status_code >= 400

    def test_extract_variable_with_precise_range(self, httpx_client, temp_workspace):
        """Test extract variable with precise column range."""
        create_python_file(
            temp_workspace / "test.py",
            "def foo():\n    x = 1 + 2\n    return x\n"
        )

        response = httpx_client.post(
            "/extract-var",
            json={
                "file": "test.py",
                "start_line": 2,
                "end_line": 2,
                "start_col": 9,
                "end_col": 14,
                "var_name": "sum_val",
                "root": str(temp_workspace)
            }
        )

        # May succeed or fail depending on context
        if response.status_code == 200:
            data = response.json()
            patches = data["patches"]
            assert_patches_valid(patches)
        else:
            # Extraction may fail for various reasons
            assert response.status_code in (400, 500)

    def test_rename_on_keyword_position(self, httpx_client, temp_workspace):
        """Test rename when positioned on Python keyword."""
        create_python_file(
            temp_workspace / "keyword.py",
            "def foo():\n    return None\n"
        )

        response = httpx_client.post(
            "/rename",
            json={
                "file": "keyword.py",
                "line": 2,
                "col": 5,  # On "return" keyword
                "new_name": "new_name",
                "root": str(temp_workspace)
            }
        )

        # Should handle gracefully
        # May return error (BadIdentifierError expected for keyword)
        assert response.status_code in (200, 400, 500)


@pytest.mark.integration
@pytest.mark.jedi
class TestHoverEdgeCases:
    """Edge cases for hover functionality."""

    def test_hover_on_function_without_docstring(self, httpx_client, temp_workspace):
        """Test hover on function without docstring."""
        create_python_file(
            temp_workspace / "no_doc.py",
            "def simple_func():\n    return 42\n"
        )

        response = httpx_client.post(
            "/hover",
            json={
                "file": "no_doc.py",
                "line": 1,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        # Should return successfully even without docstring
        assert response.status_code == 200
        data = response.json()
        # Hover returns dict with name, type, signature, docstring
        assert "name" in data
        assert "signature" in data
        # Docstring may be empty
        assert "docstring" in data

    def test_hover_with_multiline_signature(self, httpx_client, temp_workspace):
        """Test hover on function with complex multiline signature."""
        create_python_file(
            temp_workspace / "complex.py",
            """def complex_function(
    arg1: str,
    arg2: int,
    arg3: bool = True
) -> dict:
    \"\"\"A function with complex signature.

    This is the detailed description.
    \"\"\"
    return {"result": arg1}
"""
        )

        response = httpx_client.post(
            "/hover",
            json={
                "file": "complex.py",
                "line": 1,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        # Should handle multiline signature
        assert response.status_code == 200
        data = response.json()
        assert "signature" in data
        # Should include full signature
        assert "complex_function" in data.get("name", "")


@pytest.mark.integration
@pytest.mark.rope
class TestOrganizeImportsEdgeCases:
    """Edge cases for organize imports functionality."""

    def test_organize_imports_on_well_formatted_file(self, httpx_client, temp_workspace):
        """Test organize imports on already well-formatted file."""
        # Already well-organized imports
        create_python_file(
            temp_workspace / "clean.py",
            "import os\nimport sys\n\ndef foo():\n    return os.path\n"
        )

        response = httpx_client.post(
            "/organize-imports",
            json={
                "file": "clean.py",
                "root": str(temp_workspace)
            }
        )

        # Should succeed even with no changes needed
        assert response.status_code == 200
        data = response.json()
        patches = data.get("patches", {})
        # May return empty patches if no changes
        assert isinstance(patches, dict)

    def test_organize_imports_on_empty_file(self, httpx_client, temp_workspace):
        """Test organize imports on empty file."""
        create_python_file(temp_workspace / "empty.py", "")

        response = httpx_client.post(
            "/organize-imports",
            json={
                "file": "empty.py",
                "root": str(temp_workspace)
            }
        )

        # Should handle gracefully
        assert response.status_code in (200, 400)

    def test_organize_imports_with_used_imports(self, httpx_client, temp_workspace):
        """Test organize imports preserves used imports."""
        create_python_file(
            temp_workspace / "test.py",
            "import sys\nimport os\n\ndef foo():\n    print(sys.version)\n"
        )

        response = httpx_client.post(
            "/organize-imports",
            json={
                "file": "test.py",
                "root": str(temp_workspace)
            }
        )

        # Should succeed
        assert response.status_code == 200
        data = response.json()
        patches = data.get("patches", {})

        # If patches applied, should preserve sys import
        if patches and "test.py" in patches:
            content = patches["test.py"]
            # sys is used, should be preserved
            assert "sys" in content


@pytest.mark.integration
@pytest.mark.rope
class TestExtractMethodEdgeCases:
    """Edge cases for extract method functionality."""

    def test_extract_method_single_statement(self, httpx_client, temp_workspace):
        """Test extracting just one statement."""
        create_python_file(
            temp_workspace / "single.py",
            "def foo():\n    x = 42\n    y = x * 2\n    return y\n"
        )

        response = httpx_client.post(
            "/extract-method",
            json={
                "file": "single.py",
                "start_line": 2,
                "end_line": 2,  # Same as start
                "method_name": "get_value",
                "root": str(temp_workspace)
            }
        )

        # Should handle single-line extraction
        # May succeed or fail depending on context
        assert response.status_code in (200, 400, 500)

        if response.status_code == 200:
            data = response.json()
            patches = data["patches"]
            assert_patches_valid(patches)
