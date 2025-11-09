"""Test utilities and helper functions."""

import time
from pathlib import Path
from typing import Dict, Optional
import httpx


def create_python_file(path: Path, content: str) -> Path:
    """
    Helper: create .py file with content.

    Args:
        path: Path to the file to create
        content: Python code content

    Returns:
        Path to the created file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def wait_for_server_ready(port: int, timeout: float = 2.0) -> bool:
    """
    Helper: poll /health until ready or timeout.

    Args:
        port: Server port
        timeout: Maximum time to wait in seconds

    Returns:
        True if server is ready, False if timeout
    """
    start_time = time.time()
    url = f"http://127.0.0.1:{port}/health"

    while time.time() - start_time < timeout:
        try:
            response = httpx.get(url, timeout=1.0)
            if response.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        time.sleep(0.1)

    return False


def kill_all_test_servers():
    """
    Helper: cleanup any leaked test servers.

    This is a safety measure for cleanup after tests.
    """
    import psutil
    import sys

    current_pid = sys.getpid()

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any('pyclide_server' in arg for arg in cmdline):
                # Don't kill ourselves
                if proc.info['pid'] != current_pid:
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def assert_patches_valid(patches: Dict[str, str]):
    """
    Helper: validate patches dict structure.

    Args:
        patches: Dictionary mapping file paths to new content

    Raises:
        AssertionError: If patches structure is invalid
    """
    assert isinstance(patches, dict), "Patches must be a dictionary"

    for file_path, content in patches.items():
        assert isinstance(file_path, str), f"File path must be string, got {type(file_path)}"
        assert isinstance(content, str), f"Content must be string, got {type(content)}"
        assert len(content) > 0, f"Content for {file_path} is empty"


def assert_location_valid(location: dict, expected_file: Optional[str] = None):
    """
    Helper: validate location dict structure.

    Args:
        location: Location dictionary
        expected_file: Optional expected file name to check

    Raises:
        AssertionError: If location structure is invalid
    """
    assert isinstance(location, dict), "Location must be a dictionary"
    assert "file" in location, "Location must have 'file' key"
    assert "line" in location, "Location must have 'line' key"
    assert "column" in location, "Location must have 'column' key"

    assert isinstance(location["line"], int), "Line must be integer"
    assert isinstance(location["column"], int), "Column must be integer"
    assert location["line"] > 0, "Line must be positive"
    assert location["column"] >= 0, "Column must be non-negative"

    if expected_file:
        assert expected_file in location["file"], f"Expected {expected_file} in {location['file']}"


def assert_locations_response(response_data: dict, min_count: int = 1):
    """
    Helper: validate locations response structure.

    Args:
        response_data: Response data from locations endpoint
        min_count: Minimum number of expected locations

    Raises:
        AssertionError: If response structure is invalid
    """
    assert isinstance(response_data, dict), "Response must be a dictionary"
    assert "locations" in response_data, "Response must have 'locations' key"

    locations = response_data["locations"]
    assert isinstance(locations, list), "Locations must be a list"
    assert len(locations) >= min_count, f"Expected at least {min_count} locations, got {len(locations)}"

    for loc in locations:
        assert_location_valid(loc)


def assert_health_response(response_data: dict):
    """
    Helper: validate health response structure.

    Args:
        response_data: Response data from /health endpoint

    Raises:
        AssertionError: If response structure is invalid
    """
    assert isinstance(response_data, dict), "Response must be a dictionary"
    assert "status" in response_data, "Response must have 'status' key"
    assert "workspace" in response_data, "Response must have 'workspace' key"
    assert "uptime" in response_data, "Response must have 'uptime' key"
    assert "requests" in response_data, "Response must have 'requests' key"
    assert "cache_size" in response_data, "Response must have 'cache_size' key"

    assert response_data["status"] == "ok", f"Expected status 'ok', got {response_data['status']}"
    assert isinstance(response_data["uptime"], (int, float)), "Uptime must be numeric"
    assert isinstance(response_data["requests"], int), "Requests must be integer"
    assert isinstance(response_data["cache_size"], int), "Cache size must be integer"


def make_request(client, endpoint: str, method: str = "POST", **kwargs):
    """
    Helper: make HTTP request and return JSON response.

    Args:
        client: TestClient instance
        endpoint: API endpoint path
        method: HTTP method (GET, POST, etc.)
        **kwargs: Additional arguments to pass to request

    Returns:
        Response object
    """
    if method == "GET":
        return client.get(endpoint, **kwargs)
    elif method == "POST":
        return client.post(endpoint, **kwargs)
    elif method == "PUT":
        return client.put(endpoint, **kwargs)
    elif method == "DELETE":
        return client.delete(endpoint, **kwargs)
    else:
        raise ValueError(f"Unsupported method: {method}")


def get_relative_path(workspace: Path, file_path: Path) -> str:
    """
    Helper: get relative path from workspace.

    Args:
        workspace: Workspace root path
        file_path: Absolute file path

    Returns:
        Relative path as string
    """
    try:
        return str(file_path.relative_to(workspace))
    except ValueError:
        # If file is not relative to workspace, return name only
        return file_path.name
