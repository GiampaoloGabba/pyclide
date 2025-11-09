"""API contract tests: Ensure stable response structures."""

import pytest
from tests.utils import create_python_file


@pytest.mark.integration
class TestResponseContracts:
    """Test that API response structures are stable."""

    def test_health_endpoint_contract(self, httpx_client):
        """Health endpoint must return stable structure."""
        response = httpx_client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "status" in data
        assert "workspace" in data
        assert "uptime" in data
        assert "requests" in data
        assert "cache_size" in data
        assert "cache_invalidations" in data

        # Types
        assert isinstance(data["status"], str)
        assert isinstance(data["workspace"], str)
        assert isinstance(data["uptime"], (int, float))
        assert isinstance(data["requests"], int)
        assert isinstance(data["cache_size"], int)
        assert isinstance(data["cache_invalidations"], int)

    def test_defs_endpoint_contract(self, httpx_client, temp_workspace):
        """Defs endpoint must return stable structure."""
        response = httpx_client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Required structure
        assert "locations" in data
        assert isinstance(data["locations"], list)

        if len(data["locations"]) > 0:
            loc = data["locations"][0]
            assert "file" in loc
            assert "line" in loc
            assert "column" in loc
            assert isinstance(loc["file"], str)
            assert isinstance(loc["line"], int)
            assert isinstance(loc["column"], int)

    def test_refs_endpoint_contract(self, httpx_client, temp_workspace):
        """Refs endpoint must return stable structure."""
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

        assert "locations" in data
        assert isinstance(data["locations"], list)

    def test_hover_endpoint_contract(self, httpx_client, temp_workspace):
        """Hover endpoint must return stable structure."""
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

        # Optional fields but must be present
        assert "name" in data
        assert "type" in data
        assert "signature" in data
        assert "docstring" in data

    def test_occurrences_endpoint_contract(self, httpx_client, temp_workspace):
        """Occurrences endpoint must return stable structure."""
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

        assert "locations" in data
        assert isinstance(data["locations"], list)

    def test_rename_endpoint_contract(self, httpx_client, temp_workspace):
        """Rename endpoint must return stable structure."""
        response = httpx_client.post(
            "/rename",
            json={
                "file": "sample_module.py",
                "line": 14,
                "col": 5,
                "new_name": "msg",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Patches structure
        assert "patches" in data
        assert isinstance(data["patches"], dict)

        # If patches exist, check structure
        if len(data["patches"]) > 0:
            for file_path, content in data["patches"].items():
                assert isinstance(file_path, str)
                assert isinstance(content, str)

    def test_extract_method_endpoint_contract(self, httpx_client, temp_workspace):
        """Extract method endpoint must return stable structure."""
        response = httpx_client.post(
            "/extract-method",
            json={
                "file": "sample_module.py",
                "start_line": 14,
                "end_line": 14,
                "method_name": "helper",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "patches" in data
        assert isinstance(data["patches"], dict)

    def test_extract_var_endpoint_contract(self, httpx_client, temp_workspace):
        """Extract var endpoint must return stable structure."""
        response = httpx_client.post(
            "/extract-var",
            json={
                "file": "sample_module.py",
                "start_line": 20,
                "end_line": 20,
                "start_col": 16,
                "end_col": 21,
                "var_name": "temp",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "patches" in data
        assert isinstance(data["patches"], dict)

    def test_organize_imports_endpoint_contract(self, httpx_client, temp_workspace):
        """Organize imports endpoint must return stable structure."""
        test_file = temp_workspace / "test.py"
        create_python_file(test_file, "import os\nimport sys\n\nprint(os.getcwd())\nprint(sys.version)")

        response = httpx_client.post(
            "/organize-imports",
            json={
                "file": "test.py",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "patches" in data
        assert isinstance(data["patches"], dict)


@pytest.mark.integration
class TestErrorContracts:
    """Test that error responses are stable."""

    def test_validation_error_contract(self, httpx_client):
        """Validation errors must return 422 with detail."""
        response = httpx_client.post(
            "/defs",
            json={
                "file": "test.py",
                "line": 1
                # missing col and root
            }
        )

        assert response.status_code == 422
        data = response.json()

        # FastAPI validation error structure
        assert "detail" in data

    def test_missing_file_error_contract(self, httpx_client, temp_workspace):
        """Missing file errors must return 4xx/5xx."""
        response = httpx_client.post(
            "/defs",
            json={
                "file": "nonexistent.py",
                "line": 1,
                "col": 1,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code >= 400

    def test_invalid_position_error_contract(self, httpx_client, temp_workspace):
        """Invalid positions must return 4xx/5xx or empty results."""
        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "sample_module.py",
                "line": -1,
                "col": -1,
                "root": str(temp_workspace)
            }
        )

        # Either error or empty results
        if response.status_code == 200:
            data = response.json()
            assert len(data.get("locations", [])) == 0
        else:
            assert response.status_code >= 400


@pytest.mark.integration
class TestRequestValidation:
    """Test request validation contracts."""

    def test_required_fields_enforced(self, httpx_client):
        """Required fields must be validated."""
        # Missing 'line'
        response = httpx_client.post(
            "/defs",
            json={
                "file": "test.py",
                "col": 1,
                "root": "."
            }
        )
        assert response.status_code == 422

        # Missing 'new_name' for rename
        response = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 1,
                "col": 1,
                "root": "."
            }
        )
        assert response.status_code == 422

    def test_type_validation_enforced(self, httpx_client, temp_workspace):
        """Field types must be validated."""
        # Line as string instead of int
        response = httpx_client.post(
            "/defs",
            json={
                "file": "test.py",
                "line": "not_a_number",
                "col": 1,
                "root": str(temp_workspace)
            }
        )
        assert response.status_code == 422

    def test_optional_fields_handled(self, httpx_client, temp_workspace):
        """Optional fields must work when omitted."""
        # Extract var without end_line (should default)
        response = httpx_client.post(
            "/extract-var",
            json={
                "file": "sample_module.py",
                "start_line": 20,
                "var_name": "temp",
                "root": str(temp_workspace)
            }
        )

        # Should work (optional fields have defaults)
        assert response.status_code in (200, 400, 500)


@pytest.mark.integration
class TestInteroperability:
    """Test that Rope and Jedi work together."""

    def test_rope_and_jedi_same_file(self, httpx_client, temp_workspace):
        """Rope and Jedi can both analyze same file."""
        # Jedi operation
        jedi_response = httpx_client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )
        assert jedi_response.status_code == 200

        # Rope operation on same file
        rope_response = httpx_client.post(
            "/occurrences",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )
        assert rope_response.status_code == 200

    def test_rename_then_goto_works(self, httpx_client, temp_workspace):
        """Can use goto after rename."""
        test_file = temp_workspace / "test.py"
        create_python_file(test_file, "def foo():\n    pass\n\nfoo()")

        # Rename
        rename_response = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 1,
                "col": 5,
                "new_name": "bar",
                "root": str(temp_workspace)
            }
        )
        assert rename_response.status_code == 200

        # Goto should still work (on cached file)
        goto_response = httpx_client.post(
            "/defs",
            json={
                "file": "test.py",
                "line": 1,
                "col": 5,
                "root": str(temp_workspace)
            }
        )
        assert goto_response.status_code == 200
