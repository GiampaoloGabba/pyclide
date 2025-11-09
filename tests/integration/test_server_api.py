"""Integration tests for server API endpoints."""

import pytest

from tests.utils import (
    assert_health_response, assert_locations_response,
    assert_patches_valid, create_python_file
)


@pytest.mark.integration
class TestServerAPI:
    """Test server API endpoints with real engine integration."""

    def test_health_endpoint(self, httpx_client):
        """GET /health returns 200 with correct data."""
        response = httpx_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert_health_response(data)

    def test_defs_endpoint_simple(self, httpx_client, temp_workspace):
        """POST /defs returns definition locations."""
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
        assert_locations_response(data, min_count=1)

    def test_defs_endpoint_cache_hit(self, httpx_client, temp_workspace):
        """Second /defs request uses cached Jedi Script."""
        # First request
        response1 = httpx_client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )
        assert response1.status_code == 200

        # Check health to see cache size increased
        health1 = httpx_client.get("/health").json()
        cache_size_1 = health1["cache_size"]

        # Second request (should use cache)
        response2 = httpx_client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 18,  # Different position, same file
                "col": 5,
                "root": str(temp_workspace)
            }
        )
        assert response2.status_code == 200

        # Cache size should not increase
        health2 = httpx_client.get("/health").json()
        cache_size_2 = health2["cache_size"]
        assert cache_size_2 == cache_size_1

    def test_refs_endpoint(self, httpx_client, temp_workspace):
        """POST /refs returns reference locations."""
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
        assert_locations_response(data, min_count=1)

    def test_hover_endpoint(self, httpx_client, temp_workspace):
        """POST /hover returns symbol info."""
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
        assert "name" in data
        assert data["name"] == "hello_world"

    def test_occurrences_endpoint(self, httpx_client, temp_workspace):
        """POST /occurrences returns Rope occurrences."""
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

    def test_rename_endpoint(self, httpx_client, temp_workspace):
        """POST /rename returns patches dict."""
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
        assert "patches" in data
        assert_patches_valid(data["patches"])

    def test_extract_method_endpoint(self, httpx_client, temp_workspace):
        """POST /extract-method returns patches."""
        response = httpx_client.post(
            "/extract-method",
            json={
                "file": "sample_module.py",
                "start_line": 14,
                "end_line": 14,
                "method_name": "make_message",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "patches" in data
        assert_patches_valid(data["patches"])

    def test_extract_var_endpoint(self, httpx_client, temp_workspace):
        """POST /extract-var returns patches."""
        response = httpx_client.post(
            "/extract-var",
            json={
                "file": "sample_module.py",
                "start_line": 20,
                "end_line": 20,
                "start_col": 16,
                "end_col": 21,
                "var_name": "temp_result",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "patches" in data
        assert_patches_valid(data["patches"])

    def test_organize_imports_endpoint(self, httpx_client, temp_workspace):
        """POST /organize-imports returns patches."""
        # Create a file with messy imports
        test_file = temp_workspace / "messy.py"
        create_python_file(
            test_file,
            """import os
import sys

import json

def test():
    print(os.path.exists('.'))
    print(sys.version)
    return json.dumps({})
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
        # May or may not have patches depending on Rope's assessment
        assert "patches" in data

    def test_endpoint_error_handling(self, httpx_client, temp_workspace):
        """Invalid request returns 4xx/5xx with error detail."""
        # Missing required field
        response = httpx_client.post(
            "/defs",
            json={
                "file": "test.py",
                "line": 1
                # missing col and root
            }
        )

        assert response.status_code == 422  # Validation error

    def test_endpoint_nonexistent_file(self, httpx_client, temp_workspace):
        """Request with non-existent file returns error."""
        response = httpx_client.post(
            "/defs",
            json={
                "file": "nonexistent.py",
                "line": 1,
                "col": 1,
                "root": str(temp_workspace)
            }
        )

        # Should return error (500 or 404)
        assert response.status_code >= 400

    def test_shutdown_endpoint(self, httpx_client):
        """POST /shutdown triggers graceful shutdown."""
        response = httpx_client.post("/shutdown")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "shutting down" in data["status"].lower()

    def test_concurrent_requests(self, httpx_client, temp_workspace):
        """Multiple requests to different endpoints work correctly."""
        # Make requests to different endpoints in sequence
        # (TestClient is synchronous, so these are sequential)

        defs_resp = httpx_client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )
        assert defs_resp.status_code == 200

        hover_resp = httpx_client.post(
            "/hover",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )
        assert hover_resp.status_code == 200

        refs_resp = httpx_client.post(
            "/refs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )
        assert refs_resp.status_code == 200

        # All requests should succeed
        assert defs_resp.status_code == 200
        assert hover_resp.status_code == 200
        assert refs_resp.status_code == 200

    def test_request_count_incremented(self, httpx_client, temp_workspace):
        """Request increments request_count."""
        health1 = httpx_client.get("/health").json()
        initial_count = health1["requests"]

        # Make a request
        httpx_client.post(
            "/defs",
            json={
                "file": "sample_module.py",
                "line": 4,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        health2 = httpx_client.get("/health").json()
        assert health2["requests"] > initial_count
