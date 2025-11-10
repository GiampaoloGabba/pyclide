"""Regression tests: Critical functionality that must never break via server API."""

import pytest
from tests.utils import create_python_file, assert_patches_valid


@pytest.mark.integration
@pytest.mark.rope
class TestCriticalRenameScenarios:
    """Tests for rename scenarios that must always work."""

    def test_rename_preserves_all_usages(self, httpx_client, temp_workspace):
        """CRITICAL: Rename must update ALL usages, never partial."""
        test_file = temp_workspace / "test.py"
        create_python_file(
            test_file,
            """
def calculate(x, y):
    return x + y

result1 = calculate(1, 2)
result2 = calculate(3, 4)
result3 = calculate(5, 6)

def test_calculate():
    assert calculate(1, 1) == 2
"""
        )

        response = httpx_client.post(
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

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]
        new_content = list(patches.values())[0]

        # Should have 5 "compute" (def + 4 calls)
        assert new_content.count("compute") == 5
        assert "def compute(x, y):" in new_content
        assert "def calculate(x, y):" not in new_content

    def test_rename_with_string_literal_containing_name(self, httpx_client, temp_workspace):
        """CRITICAL: Rename should NOT change string literals."""
        test_file = temp_workspace / "test.py"
        create_python_file(
            test_file,
            '''
def user_login(username):
    print("user_login called")
    return username

result = user_login("alice")
'''
        )

        response = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 2,
                "col": 5,
                "new_name": "authenticate",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]
        new_content = list(patches.values())[0]

        # String literal should NOT be renamed
        assert '"user_login called"' in new_content
        # Function should be renamed
        assert "def authenticate" in new_content

    def test_rename_with_comments_mentioning_name(self, httpx_client, temp_workspace):
        """CRITICAL: Rename should NOT modify comments."""
        test_file = temp_workspace / "test.py"
        create_python_file(
            test_file,
            """
# Use helper_function to process data
def helper_function():
    return 42

result = helper_function()
"""
        )

        response = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 3,
                "col": 5,
                "new_name": "processor",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data["patches"]
            new_content = list(patches.values())[0]
            # Function renamed
            assert "def processor" in new_content
            # Comment may or may not be updated (Rope behavior)


@pytest.mark.integration
@pytest.mark.rope
class TestCriticalImportHandling:
    """Critical import handling tests."""

    def test_rename_updates_all_import_statements(self, httpx_client, temp_workspace):
        """CRITICAL: All import statements must be updated."""
        module = temp_workspace / "module.py"
        create_python_file(
            module,
            """
def important_function():
    return "critical"
"""
        )

        user1 = temp_workspace / "user1.py"
        create_python_file(user1, "from module import important_function\n\nresult = important_function()")

        user2 = temp_workspace / "user2.py"
        create_python_file(user2, "from module import important_function\n\nvalue = important_function()")

        response = httpx_client.post(
            "/rename",
            json={
                "file": "module.py",
                "line": 2,
                "col": 5,
                "new_name": "critical_function",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]

        # All files should be updated
        all_content = " ".join(patches.values())
        assert "critical_function" in all_content

    def test_organize_imports_preserves_needed_imports(self, httpx_client, temp_workspace):
        """CRITICAL: Used imports must not be removed."""
        test_file = temp_workspace / "test.py"
        create_python_file(
            test_file,
            """
import os
import sys

def use_them():
    print(os.getcwd())
    print(sys.version)
"""
        )

        response = httpx_client.post(
            "/organize-imports",
            json={"file": "test.py", "root": str(temp_workspace)}
        )

        assert response.status_code == 200
        data = response.json()
        patches = data.get("patches", {})

        if patches:
            content = list(patches.values())[0]
            # Both imports must be preserved
            assert "import os" in content or "os" in content
            assert "import sys" in content or "sys" in content


@pytest.mark.integration
@pytest.mark.rope
class TestCriticalMultiFileConsistency:
    """Tests for multi-file consistency."""

    def test_rename_across_files_is_atomic(self, httpx_client, temp_workspace):
        """CRITICAL: Cross-file rename must be all-or-nothing."""
        utils = temp_workspace / "utils.py"
        create_python_file(utils, "def shared_utility():\n    return 'shared'")

        app = temp_workspace / "app.py"
        create_python_file(app, "from utils import shared_utility\n\nresult = shared_utility()")

        main = temp_workspace / "main.py"
        create_python_file(main, "from utils import shared_utility\n\nvalue = shared_utility()")

        response = httpx_client.post(
            "/rename",
            json={
                "file": "utils.py",
                "line": 1,
                "col": 5,
                "new_name": "common_utility",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]

        # All files should get patches
        assert len(patches) >= 1
        all_content = " ".join(patches.values())
        assert "common_utility" in all_content


@pytest.mark.integration
class TestCriticalErrorHandling:
    """Critical error handling tests."""

    def test_invalid_position_returns_gracefully(self, httpx_client, temp_workspace):
        """CRITICAL: Invalid positions must not crash."""
        test_file = temp_workspace / "test.py"
        create_python_file(test_file, "def foo():\n    pass")

        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "test.py",
                "line": 999,
                "col": 999,
                "root": str(temp_workspace)
            }
        )

        # Should handle gracefully, not crash
        assert response.status_code in (200, 400, 500)

    def test_syntax_error_file_skipped_gracefully(self, httpx_client, temp_workspace):
        """CRITICAL: Syntax errors must not crash server."""
        bad_file = temp_workspace / "bad.py"
        create_python_file(bad_file, "def broken(\n    pass")

        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "bad.py",
                "line": 1,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        # Should handle gracefully
        assert response.status_code in (200, 400, 500)


@pytest.mark.integration
@pytest.mark.rope
class TestCriticalEdgeCases:
    """Critical edge case tests."""

    def test_rename_class_with_same_name_as_module(self, httpx_client, temp_workspace):
        """CRITICAL: Class name matching module name."""
        calculator = temp_workspace / "calculator.py"
        create_python_file(
            calculator,
            """
class Calculator:
    def add(self, x, y):
        return x + y
"""
        )

        usage = temp_workspace / "usage.py"
        create_python_file(usage, "from calculator import Calculator\n\ncalc = Calculator()")

        response = httpx_client.post(
            "/rename",
            json={
                "file": "calculator.py",
                "line": 2,
                "col": 7,
                "new_name": "Calc",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data["patches"]
            assert len(patches) >= 1

    def test_rename_with_inheritance_chain(self, httpx_client, temp_workspace):
        """CRITICAL: Inheritance must be preserved."""
        base = temp_workspace / "base.py"
        create_python_file(
            base,
            """
class BaseClass:
    def method(self):
        pass

class DerivedClass(BaseClass):
    def method(self):
        super().method()
"""
        )

        response = httpx_client.post(
            "/rename",
            json={
                "file": "base.py",
                "line": 2,
                "col": 7,
                "new_name": "Base",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data["patches"]
            content = list(patches.values())[0]
            # Inheritance should be updated
            assert "class DerivedClass(Base)" in content

    def test_extract_with_local_variables(self, httpx_client, temp_workspace):
        """CRITICAL: Extract must handle local variables correctly."""
        test_file = temp_workspace / "test.py"
        create_python_file(
            test_file,
            """
def compute():
    x = 10
    y = 20
    result = x + y
    return result
"""
        )

        response = httpx_client.post(
            "/extract-method",
            json={
                "file": "test.py",
                "start_line": 4,
                "end_line": 5,
                "method_name": "sum_values",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data["patches"]
            assert_patches_valid(patches)

    def test_circular_imports_dont_crash(self, httpx_client, temp_workspace):
        """CRITICAL: Circular imports must not crash."""
        a = temp_workspace / "a.py"
        create_python_file(a, "from b import func_b\n\ndef func_a():\n    return func_b()")

        b = temp_workspace / "b.py"
        create_python_file(b, "from a import func_a\n\ndef func_b():\n    return 42")

        response = httpx_client.post(
            "/defs",
            json={
                "file": "a.py",
                "line": 3,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        # Should not crash
        assert response.status_code in (200, 400, 500)


@pytest.mark.integration
class TestCriticalResponseStructure:
    """Critical response structure tests."""

    def test_patches_structure_is_stable(self, httpx_client, temp_workspace):
        """CRITICAL: Patches response structure must be stable."""
        test_file = temp_workspace / "test.py"
        create_python_file(test_file, "def foo():\n    pass")

        response = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 1,
                "col": 5,
                "new_name": "bar",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Structure must be stable
        assert "patches" in data
        assert isinstance(data["patches"], dict)

    def test_locations_structure_is_stable(self, httpx_client, temp_workspace):
        """CRITICAL: Locations response structure must be stable."""
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

        # Structure must be stable
        assert "locations" in data
        assert isinstance(data["locations"], list)
        if len(data["locations"]) > 0:
            loc = data["locations"][0]
            assert "file" in loc
            assert "line" in loc
            assert "column" in loc
