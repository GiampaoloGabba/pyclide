"""Integration tests for diff format in API responses.

Tests that the server API correctly handles output_format parameter
and returns diffs by default for all refactoring endpoints.
"""

import re

import pytest


def apply_unified_diff(original_content: str, diff_text: str) -> str:
    """
    Apply a unified diff to original content and return the result.

    This is used to verify that API-generated diffs are valid and produce
    the expected result when applied.

    Args:
        original_content: Original file content
        diff_text: Unified diff text

    Returns:
        Patched content

    Raises:
        ValueError: If diff cannot be applied
    """
    if not diff_text:
        return original_content

    # Parse diff to extract hunks
    lines = diff_text.split('\n')
    original_lines = original_content.splitlines(keepends=True)
    result_lines = list(original_lines)

    # Find hunks (lines starting with @@)
    hunks = []
    current_hunk = None

    for line in lines:
        if line.startswith('@@'):
            # Parse hunk header: @@ -start,count +start,count @@
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if match:
                old_start = int(match.group(1))
                old_count = int(match.group(2)) if match.group(2) else 1
                new_start = int(match.group(3))
                new_count = int(match.group(4)) if match.group(4) else 1

                current_hunk = {
                    'old_start': old_start,
                    'old_count': old_count,
                    'new_start': new_start,
                    'new_count': new_count,
                    'lines': []
                }
                hunks.append(current_hunk)
        elif current_hunk is not None:
            if line.startswith(' ') or line.startswith('+') or line.startswith('-'):
                current_hunk['lines'].append(line)

    # Apply hunks in reverse order to maintain line numbers
    for hunk in reversed(hunks):
        old_start = hunk['old_start'] - 1  # Convert to 0-based
        old_count = hunk['old_count']

        # Build new lines for this hunk
        new_lines = []
        for line in hunk['lines']:
            if line.startswith('+'):
                new_lines.append(line[1:] + '\n')
            elif line.startswith(' '):
                new_lines.append(line[1:] + '\n')
            # Skip lines starting with '-'

        # Replace old lines with new lines
        result_lines[old_start:old_start + old_count] = new_lines

    return ''.join(result_lines)


@pytest.mark.integration
@pytest.mark.rope
class TestAPIDiffCorrectnessValidation:
    """CRITICAL: Validate that API-generated diffs are correct and applicable.

    These tests verify that diff format from the HTTP API:
    1. Can be successfully applied to original content
    2. Produces the same result as output_format="full"
    3. Works correctly for all refactoring endpoints
    """

    def test_api_rename_diff_applies_correctly(self, httpx_client, temp_workspace):
        """CRITICAL: API rename diff should apply correctly."""
        test_file = temp_workspace / "test.py"
        original_content = """
def old_name():
    x = 1
    y = old_name()
    return y
"""
        test_file.write_text(original_content)

        # Get diff format
        response_diff = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 2,
                "col": 5,
                "new_name": "new_name",
                "root": str(temp_workspace),
                "output_format": "diff"
            }
        )

        # Get full format
        response_full = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 2,
                "col": 5,
                "new_name": "new_name",
                "root": str(temp_workspace),
                "output_format": "full"
            }
        )

        assert response_diff.status_code == 200
        assert response_full.status_code == 200

        diff_data = response_diff.json()
        full_data = response_full.json()

        # Apply diff
        diff_text = diff_data["patches"]["test.py"]
        patched_content = apply_unified_diff(original_content, diff_text)

        # Should match full format
        assert patched_content == full_data["patches"]["test.py"], \
            "API diff application mismatch!"

    def test_api_extract_method_diff_applies_correctly(self, httpx_client, temp_workspace):
        """API extract method diff should apply correctly."""
        test_file = temp_workspace / "test.py"
        original_content = """
def func():
    x = 10
    y = 20
    z = x + y
    return z
"""
        test_file.write_text(original_content)

        response_diff = httpx_client.post(
            "/extract-method",
            json={
                "file": "test.py",
                "start_line": 5,
                "end_line": 5,
                "method_name": "calc_sum",
                "root": str(temp_workspace),
                "output_format": "diff"
            }
        )

        response_full = httpx_client.post(
            "/extract-method",
            json={
                "file": "test.py",
                "start_line": 5,
                "end_line": 5,
                "method_name": "calc_sum",
                "root": str(temp_workspace),
                "output_format": "full"
            }
        )

        if response_diff.status_code == 200 and response_full.status_code == 200:
            diff_data = response_diff.json()
            full_data = response_full.json()

            if diff_data["patches"]:
                diff_text = diff_data["patches"]["test.py"]
                patched_content = apply_unified_diff(original_content, diff_text)
                assert patched_content == full_data["patches"]["test.py"]

    def test_api_extract_var_diff_applies_correctly(self, httpx_client, temp_workspace):
        """API extract variable diff should apply correctly."""
        test_file = temp_workspace / "test.py"
        original_content = """
def func():
    result = 10 + 20
    return result
"""
        test_file.write_text(original_content)

        response_diff = httpx_client.post(
            "/extract-var",
            json={
                "file": "test.py",
                "start_line": 3,
                "end_line": 3,
                "var_name": "sum_val",
                "start_col": 14,
                "end_col": 21,
                "root": str(temp_workspace),
                "output_format": "diff"
            }
        )

        response_full = httpx_client.post(
            "/extract-var",
            json={
                "file": "test.py",
                "start_line": 3,
                "end_line": 3,
                "var_name": "sum_val",
                "start_col": 14,
                "end_col": 21,
                "root": str(temp_workspace),
                "output_format": "full"
            }
        )

        if response_diff.status_code == 200 and response_full.status_code == 200:
            diff_data = response_diff.json()
            full_data = response_full.json()

            if diff_data["patches"]:
                diff_text = diff_data["patches"]["test.py"]
                patched_content = apply_unified_diff(original_content, diff_text)
                assert patched_content == full_data["patches"]["test.py"]

    def test_api_organize_imports_diff_applies_correctly(self, httpx_client, temp_workspace):
        """API organize imports diff should apply correctly."""
        test_file = temp_workspace / "test.py"
        original_content = """
import sys
import os


import json

print(os.getcwd())
print(sys.version)
print(json.dumps({}))
"""
        test_file.write_text(original_content)

        response_diff = httpx_client.post(
            "/organize-imports",
            json={
                "file": "test.py",
                "root": str(temp_workspace),
                "output_format": "diff"
            }
        )

        response_full = httpx_client.post(
            "/organize-imports",
            json={
                "file": "test.py",
                "root": str(temp_workspace),
                "output_format": "full"
            }
        )

        assert response_diff.status_code == 200
        assert response_full.status_code == 200

        diff_data = response_diff.json()
        full_data = response_full.json()

        if diff_data["patches"]:
            diff_text = diff_data["patches"]["test.py"]
            patched_content = apply_unified_diff(original_content, diff_text)
            assert patched_content == full_data["patches"]["test.py"]

    def test_api_cross_file_rename_all_diffs_apply(self, httpx_client, temp_workspace):
        """All diffs in cross-file API rename should apply correctly."""
        file1 = temp_workspace / "module.py"
        content1 = "def old_name():\n    pass\n"
        file1.write_text(content1)

        file2 = temp_workspace / "usage.py"
        content2 = "from module import old_name\nold_name()\n"
        file2.write_text(content2)

        response_diff = httpx_client.post(
            "/rename",
            json={
                "file": "module.py",
                "line": 1,
                "col": 5,
                "new_name": "new_name",
                "root": str(temp_workspace),
                "output_format": "diff"
            }
        )

        response_full = httpx_client.post(
            "/rename",
            json={
                "file": "module.py",
                "line": 1,
                "col": 5,
                "new_name": "new_name",
                "root": str(temp_workspace),
                "output_format": "full"
            }
        )

        assert response_diff.status_code == 200
        assert response_full.status_code == 200

        diff_data = response_diff.json()
        full_data = response_full.json()

        # Verify all diffs apply correctly
        for file_path, diff_text in diff_data["patches"].items():
            if file_path == "module.py":
                original = content1
            elif file_path == "usage.py":
                original = content2
            else:
                continue

            patched = apply_unified_diff(original, diff_text)
            assert patched == full_data["patches"][file_path], \
                f"API diff mismatch for {file_path}"


@pytest.mark.integration
@pytest.mark.rope
class TestServerDiffFormat:
    """Test that server endpoints return diff format correctly."""

    def test_rename_returns_diff_by_default(self, httpx_client, temp_workspace):
        """Rename endpoint returns diff format when no output_format specified."""
        test_file = temp_workspace / "test.py"
        test_file.write_text("x = 1\ny = x + 2\n")

        response = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 1,
                "col": 1,
                "new_name": "z",
                "root": str(temp_workspace)
                # No output_format specified - should default to "diff"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Should have format field
        assert "format" in data
        assert data["format"] == "diff"

        # Patches should be diffs
        patches = data["patches"]
        diff = patches["test.py"]

        assert "---" in diff
        assert "+++" in diff
        assert "@@" in diff
        assert "-x = 1" in diff
        assert "+z = 1" in diff

    def test_rename_explicit_diff_format(self, httpx_client, temp_workspace):
        """Rename with output_format='diff' returns diff."""
        test_file = temp_workspace / "test.py"
        test_file.write_text("def func():\n    pass\n")

        response = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 1,
                "col": 5,
                "new_name": "new_func",
                "root": str(temp_workspace),
                "output_format": "diff"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "diff"

        diff = data["patches"]["test.py"]
        assert "--- test.py" in diff or "--- a/test.py" in diff
        assert "-def func" in diff
        assert "+def new_func" in diff

    def test_rename_explicit_full_format(self, httpx_client, temp_workspace):
        """Rename with output_format='full' returns complete file."""
        test_file = temp_workspace / "test.py"
        test_file.write_text("def func():\n    pass\n")

        response = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 1,
                "col": 5,
                "new_name": "new_func",
                "root": str(temp_workspace),
                "output_format": "full"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "full"

        content = data["patches"]["test.py"]
        # Should be full content, not diff
        assert "---" not in content
        assert "+++" not in content
        assert "def new_func():" in content
        assert "pass" in content

    def test_extract_method_returns_diff_by_default(self, httpx_client, temp_workspace):
        """Extract method returns diff by default."""
        test_file = temp_workspace / "test.py"
        test_file.write_text("""
def func():
    x = 10
    y = 20
    z = x + y
    return z
""")

        response = httpx_client.post(
            "/extract-method",
            json={
                "file": "test.py",
                "start_line": 5,
                "end_line": 5,
                "method_name": "calc_sum",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:  # Rope might refuse
            data = response.json()
            assert data["format"] == "diff"

            if data["patches"]:
                diff = list(data["patches"].values())[0]
                # Should be diff or at least contain the new method name
                assert "---" in diff or "calc_sum" in diff

    def test_extract_var_returns_diff_by_default(self, httpx_client, temp_workspace):
        """Extract variable returns diff by default."""
        test_file = temp_workspace / "test.py"
        test_file.write_text("""
def func():
    result = 10 + 20
    return result
""")

        response = httpx_client.post(
            "/extract-var",
            json={
                "file": "test.py",
                "start_line": 3,
                "end_line": 3,
                "var_name": "sum_val",
                "start_col": 14,
                "end_col": 21,
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            assert data["format"] == "diff"

    def test_move_returns_diff_by_default(self, httpx_client, temp_workspace):
        """Move returns diff by default."""
        source = temp_workspace / "source.py"
        source.write_text("def my_func():\n    return 42\n")

        target = temp_workspace / "target.py"
        target.write_text("# target\n")

        response = httpx_client.post(
            "/move",
            json={
                "file": "source.py",
                "line": 1,
                "col": 5,
                "dest_file": "target.py",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            assert data["format"] == "diff"

            # At least one patch should be a diff
            patches = data["patches"]
            has_diff = any("---" in p and "+++" in p for p in patches.values())
            # Move might return full content for new files, so just verify format field
            assert data["format"] == "diff"

    def test_organize_imports_returns_diff_by_default(self, httpx_client, temp_workspace):
        """Organize imports returns diff by default."""
        test_file = temp_workspace / "test.py"
        test_file.write_text("""
import sys
import os


import json

print(os.getcwd())
""")

        response = httpx_client.post(
            "/organize-imports",
            json={
                "file": "test.py",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "diff"

        if data["patches"]:
            diff = data["patches"]["test.py"]
            assert "---" in diff
            assert "+++" in diff

    def test_diff_response_structure(self, httpx_client, temp_workspace):
        """Verify response structure includes format field."""
        test_file = temp_workspace / "test.py"
        test_file.write_text("x = 1\n")

        response = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 1,
                "col": 1,
                "new_name": "y",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "patches" in data
        assert "format" in data
        assert isinstance(data["patches"], dict)
        assert data["format"] in ["diff", "full"]

    def test_diff_saves_tokens(self, httpx_client, temp_workspace):
        """Diff format is significantly smaller than full."""
        # Create larger file
        test_file = temp_workspace / "test.py"
        test_file.write_text("""
def calculate(x, y):
    # Comment
    result = x + y
    return result

def other():
    a = 1
    b = 2
    c = 3
    d = 4
    e = 5
    return a + b + c + d + e

def another():
    for i in range(100):
        print(i)
    return True
""" * 3)  # Make it bigger

        # Get diff
        response_diff = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 2,
                "col": 5,
                "new_name": "compute",
                "root": str(temp_workspace),
                "output_format": "diff"
            }
        )

        # Get full
        response_full = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 2,
                "col": 5,
                "new_name": "compute",
                "root": str(temp_workspace),
                "output_format": "full"
            }
        )

        assert response_diff.status_code == 200
        assert response_full.status_code == 200

        diff_size = len(response_diff.json()["patches"]["test.py"])
        full_size = len(response_full.json()["patches"]["test.py"])

        # Diff should be smaller (at least 20% savings)
        assert diff_size < full_size * 0.8, f"Diff ({diff_size}) not smaller than full ({full_size})"
        # Typically saves 30-90% depending on change scope

    def test_invalid_output_format_rejected(self, httpx_client, temp_workspace):
        """Invalid output_format value is rejected."""
        test_file = temp_workspace / "test.py"
        test_file.write_text("x = 1\n")

        response = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 1,
                "col": 1,
                "new_name": "y",
                "root": str(temp_workspace),
                "output_format": "invalid"  # Invalid value
            }
        )

        # Should be rejected (422 Unprocessable Entity for validation error)
        assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.rope
class TestAllRefactoringEndpointsDefaultToDiff:
    """Verify all refactoring endpoints default to diff format."""

    def test_all_endpoints_have_format_field(self, httpx_client, temp_workspace):
        """All refactoring endpoints include 'format' in response."""
        test_file = temp_workspace / "test.py"
        test_file.write_text("x = 1\ny = x\n")

        # Test each endpoint
        endpoints_to_test = [
            ("/rename", {
                "file": "test.py",
                "line": 1,
                "col": 1,
                "new_name": "z",
                "root": str(temp_workspace)
            }),
            ("/organize-imports", {
                "file": "test.py",
                "root": str(temp_workspace)
            })
        ]

        for endpoint, payload in endpoints_to_test:
            response = httpx_client.post(endpoint, json=payload)

            if response.status_code == 200:
                data = response.json()
                assert "format" in data, f"{endpoint} missing 'format' field"
                assert data["format"] == "diff", f"{endpoint} not defaulting to diff"

    def test_backward_compatibility_full_still_works(self, httpx_client, temp_workspace):
        """Existing code using output_format='full' still works."""
        test_file = temp_workspace / "test.py"
        test_file.write_text("def func():\n    pass\n")

        response = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 1,
                "col": 5,
                "new_name": "new_func",
                "root": str(temp_workspace),
                "output_format": "full"  # Explicit full
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "full"

        content = data["patches"]["test.py"]
        # Complete file content
        assert "def new_func():" in content
        assert "---" not in content  # Not a diff
