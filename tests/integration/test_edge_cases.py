"""Integration tests for edge cases and error handling on server API."""

import pytest

from tests.utils import create_python_file


@pytest.mark.integration
class TestInvalidFileOperations:
    """Test server handling of invalid file operations."""

    def test_nonexistent_file(self, httpx_client, temp_workspace):
        """Test operations on non-existent file return error."""
        response = httpx_client.post(
            "/defs",
            json={
                "file": "nonexistent.py",
                "line": 1,
                "col": 1,
                "root": str(temp_workspace)
            }
        )

        # Should return error (500)
        assert response.status_code >= 400

    def test_empty_file_path(self, httpx_client, temp_workspace):
        """Test with empty file path."""
        response = httpx_client.post(
            "/defs",
            json={
                "file": "",
                "line": 1,
                "col": 1,
                "root": str(temp_workspace)
            }
        )

        # Should return error
        assert response.status_code >= 400

    def test_non_python_file(self, httpx_client, temp_workspace):
        """Test operations on non-Python file."""
        # Create a text file
        txt_file = temp_workspace / "test.txt"
        txt_file.write_text("This is not Python code", encoding="utf-8")

        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "test.txt",
                "line": 1,
                "col": 1,
                "root": str(temp_workspace)
            }
        )

        # May fail or return empty results - both acceptable
        # Just ensure it doesn't crash the server
        assert response.status_code in (200, 400, 500)

    def test_directory_as_file(self, httpx_client, temp_workspace):
        """Test operations when a directory is specified as file."""
        # Create a directory
        dir_path = temp_workspace / "somedir"
        dir_path.mkdir()

        response = httpx_client.post(
            "/defs",
            json={
                "file": "somedir",
                "line": 1,
                "col": 1,
                "root": str(temp_workspace)
            }
        )

        # Should return error
        assert response.status_code >= 400


@pytest.mark.integration
class TestInvalidPositions:
    """Test server handling of invalid line/column positions."""

    def test_line_zero(self, httpx_client, temp_workspace):
        """Test with line 0 (invalid, 1-based indexing)."""
        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "sample_module.py",
                "line": 0,
                "col": 1,
                "root": str(temp_workspace)
            }
        )

        # Should return error or handle gracefully
        # Line 0 is invalid in 1-based indexing
        assert response.status_code >= 400 or (
            response.status_code == 200 and len(response.json().get("locations", [])) == 0
        )

    def test_negative_line(self, httpx_client, temp_workspace):
        """Test with negative line number."""
        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "sample_module.py",
                "line": -1,
                "col": 1,
                "root": str(temp_workspace)
            }
        )

        # Should return error
        assert response.status_code >= 400 or (
            response.status_code == 200 and len(response.json().get("locations", [])) == 0
        )

    def test_negative_column(self, httpx_client, temp_workspace):
        """Test with negative column number."""
        response = httpx_client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 1,
                "col": -1,
                "root": str(temp_workspace)
            }
        )

        # Should handle gracefully (may clamp to 0 or return error)
        assert response.status_code in (200, 400, 500)

    def test_line_exceeds_file_length(self, httpx_client, temp_workspace):
        """Test with line number greater than file length."""
        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "sample_module.py",  # ~57 lines
                "line": 1000,
                "col": 1,
                "root": str(temp_workspace)
            }
        )

        # May return empty results or error
        if response.status_code == 200:
            data = response.json()
            # Should return empty locations
            assert len(data.get("locations", [])) == 0
        else:
            # Or may return error
            assert response.status_code >= 400

    def test_column_exceeds_line_length(self, httpx_client, temp_workspace):
        """Test with column greater than line length."""
        response = httpx_client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,  # "def hello_world(name: str) -> str:"
                "col": 1000,  # Way beyond line length
                "root": str(temp_workspace)
            }
        )

        # Should handle gracefully (clamp or return empty)
        if response.status_code == 200:
            # May return empty results
            data = response.json()
            assert isinstance(data.get("locations", []), list)
        else:
            # Or may error
            assert response.status_code >= 400

    def test_empty_file_any_position(self, httpx_client, temp_workspace):
        """Test operations on empty file."""
        # Create empty file
        empty_file = temp_workspace / "empty.py"
        empty_file.write_text("", encoding="utf-8")

        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "empty.py",
                "line": 1,
                "col": 1,
                "root": str(temp_workspace)
            }
        )

        # Should handle gracefully
        if response.status_code == 200:
            data = response.json()
            # Should return empty locations
            assert len(data.get("locations", [])) == 0
        else:
            # Or may return error
            assert response.status_code >= 400


@pytest.mark.integration
class TestInvalidPythonSyntax:
    """Test server handling of files with syntax errors."""

    def test_syntax_error_file_jedi(self, httpx_client, temp_workspace):
        """Test Jedi operations on file with syntax error."""
        # Create file with syntax error
        bad_file = temp_workspace / "bad_syntax.py"
        create_python_file(bad_file, "def broken(\n    pass")

        response = httpx_client.post(
            "/defs",
            json={
                "file": "bad_syntax.py",
                "line": 1,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        # Jedi may handle gracefully or fail
        # Just ensure server doesn't crash
        assert response.status_code in (200, 400, 500)

    def test_syntax_error_file_rope(self, httpx_client, temp_workspace):
        """Test Rope operations on file with syntax error."""
        # Create file with syntax error
        bad_file = temp_workspace / "bad_rope.py"
        create_python_file(bad_file, "def broken(\n    pass")

        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "bad_rope.py",
                "line": 1,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        # Rope with ignore_syntax_errors=True should handle gracefully
        if response.status_code == 200:
            data = response.json()
            # Should return empty or handle gracefully
            assert isinstance(data.get("locations", []), list)
        else:
            # May return error
            assert response.status_code >= 400

    def test_incomplete_code(self, httpx_client, temp_workspace):
        """Test with incomplete Python code."""
        # Create incomplete class
        incomplete = temp_workspace / "incomplete.py"
        create_python_file(incomplete, "class Foo:")  # No body

        response = httpx_client.post(
            "/hover",
            json={
                "file": "incomplete.py",
                "line": 1,
                "col": 7,
                "root": str(temp_workspace)
            }
        )

        # May work or fail - just ensure no crash
        assert response.status_code in (200, 400, 500)

    def test_file_with_unicode_errors(self, httpx_client, temp_workspace):
        """Test file with encoding issues."""
        # Create file with potential encoding issues
        unicode_file = temp_workspace / "unicode_test.py"
        create_python_file(unicode_file, '# Comment with émojis 🔥\ndef test():\n    return "hello"')

        response = httpx_client.post(
            "/defs",
            json={
                "file": "unicode_test.py",
                "line": 2,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        # Should handle Unicode properly
        assert response.status_code == 200


@pytest.mark.integration
class TestOperationFailures:
    """Test Rope and Jedi operation failures."""

    def test_symbol_not_found_at_position(self, httpx_client, temp_workspace):
        """Test when no symbol exists at the given position."""
        # Create file with just a comment
        comment_file = temp_workspace / "comment.py"
        create_python_file(comment_file, "# Just a comment\n")

        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "comment.py",
                "line": 1,
                "col": 5,  # On the comment
                "root": str(temp_workspace)
            }
        )

        # Should return empty results
        if response.status_code == 200:
            data = response.json()
            assert len(data.get("locations", [])) == 0
        else:
            # Or may error
            assert response.status_code >= 400

    def test_rename_on_whitespace(self, httpx_client, temp_workspace):
        """Test rename on whitespace/invalid position."""
        # Create simple file
        test_file = temp_workspace / "whitespace_test.py"
        create_python_file(test_file, "def foo():\n    pass\n")

        response = httpx_client.post(
            "/rename",
            json={
                "file": "whitespace_test.py",
                "line": 2,
                "col": 1,  # On whitespace before "pass"
                "new_name": "new_name",
                "root": str(temp_workspace)
            }
        )

        # Should return empty patches or error
        if response.status_code == 200:
            data = response.json()
            patches = data.get("patches", {})
            # May return empty patches
            assert isinstance(patches, dict)
        else:
            assert response.status_code >= 400

    def test_extract_invalid_range(self, httpx_client, temp_workspace):
        """Test extract method with invalid range (end < start)."""
        # Create file
        test_file = temp_workspace / "extract_test.py"
        create_python_file(test_file, "def foo():\n    x = 1\n    y = 2\n")

        response = httpx_client.post(
            "/extract-method",
            json={
                "file": "extract_test.py",
                "start_line": 3,
                "end_line": 2,  # End before start
                "method_name": "extracted",
                "root": str(temp_workspace)
            }
        )

        # Should return error
        assert response.status_code >= 400

    def test_extract_variable_on_statement(self, httpx_client, temp_workspace):
        """Test extract variable on statement (not expression)."""
        # Create file
        test_file = temp_workspace / "extract_stmt.py"
        create_python_file(test_file, "def foo():\n    return\n")

        response = httpx_client.post(
            "/extract-var",
            json={
                "file": "extract_stmt.py",
                "start_line": 2,
                "end_line": 2,
                "start_col": 5,
                "end_col": 11,  # "return" keyword
                "var_name": "extracted",
                "root": str(temp_workspace)
            }
        )

        # Should fail - can't extract statement as variable
        # May return error or empty patches
        if response.status_code == 200:
            data = response.json()
            # Empty patches acceptable
            assert isinstance(data.get("patches", {}), dict)
        else:
            assert response.status_code >= 400

    def test_rename_builtin(self, httpx_client, temp_workspace):
        """Test rename on builtin function."""
        # Create file using a builtin
        builtin_file = temp_workspace / "builtin_test.py"
        create_python_file(builtin_file, "x = len([1, 2, 3])\n")

        response = httpx_client.post(
            "/rename",
            json={
                "file": "builtin_test.py",
                "line": 1,
                "col": 5,  # On "len"
                "new_name": "my_len",
                "root": str(temp_workspace)
            }
        )

        # Should handle gracefully (can't rename builtins)
        if response.status_code == 200:
            data = response.json()
            patches = data.get("patches", {})
            # Should return empty patches (can't rename builtin)
            assert isinstance(patches, dict)
        else:
            assert response.status_code >= 400

    def test_goto_definition_on_literal(self, httpx_client, temp_workspace):
        """Test goto definition on literal value."""
        # Create file with literals
        literal_file = temp_workspace / "literal.py"
        create_python_file(literal_file, 'x = "hello"\ny = 42\n')

        response = httpx_client.post(
            "/defs",
            json={
                "file": "literal.py",
                "line": 1,
                "col": 6,  # On the string literal
                "root": str(temp_workspace)
            }
        )

        # Should return empty or handle gracefully
        if response.status_code == 200:
            data = response.json()
            # May return empty locations
            assert isinstance(data.get("locations", []), list)
        else:
            assert response.status_code >= 400


@pytest.mark.integration
class TestMalformedRequests:
    """Test server handling of malformed requests."""

    def test_missing_required_field(self, httpx_client):
        """Test request missing required field."""
        response = httpx_client.post(
            "/defs",
            json={
                "file": "test.py",
                "line": 1
                # missing col and root
            }
        )

        # Should return validation error (422)
        assert response.status_code == 422

    def test_invalid_type_for_line(self, httpx_client, temp_workspace):
        """Test invalid type for line field."""
        response = httpx_client.post(
            "/defs",
            json={
                "file": "test.py",
                "line": "not_a_number",
                "col": 1,
                "root": str(temp_workspace)
            }
        )

        # Should return validation error
        assert response.status_code == 422

    def test_empty_json_body(self, httpx_client):
        """Test request with empty JSON body."""
        response = httpx_client.post("/defs", json={})

        # Should return validation error
        assert response.status_code == 422

    def test_invalid_json(self, httpx_client):
        """Test request with invalid JSON."""
        response = httpx_client.post(
            "/defs",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )

        # Should return error
        assert response.status_code >= 400
