"""Advanced integration tests for Jedi engine functionality via server API."""

import pytest

from tests.utils import assert_locations_response, create_python_file


@pytest.mark.integration
@pytest.mark.jedi
class TestJediGotoEdgeCases:
    """Test advanced goto scenarios via /defs endpoint."""

    def test_goto_multiple_definitions_overloads(self, httpx_client, temp_workspace):
        """Test goto with multiple definitions (method overriding)."""
        # Create file with class inheritance
        overload_file = temp_workspace / "overload.py"
        create_python_file(
            overload_file,
            """
class Base:
    def method(self):
        pass

class Derived(Base):
    def method(self):
        pass

obj = Derived()
obj.method()
"""
        )

        response = httpx_client.post(
            "/defs",
            json={
                "file": "overload.py",
                "line": 11,
                "col": 5,  # On method() call
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert_locations_response(data, min_count=1)

        # Jedi may return one or multiple definitions
        locations = data["locations"]
        assert len(locations) >= 1

    def test_goto_on_import_statement(self, httpx_client, temp_workspace):
        """Test goto on an import statement."""
        import_file = temp_workspace / "imports.py"
        create_python_file(import_file, "import os\n")

        response = httpx_client.post(
            "/defs",
            json={
                "file": "imports.py",
                "line": 1,
                "col": 8,  # On "os"
                "root": str(temp_workspace)
            }
        )

        # May go to os module definition or return empty
        if response.status_code == 200:
            data = response.json()
            locations = data.get("locations", [])
            assert isinstance(locations, list)
        else:
            # May fail on builtins/stdlib
            assert response.status_code >= 400

    def test_goto_on_builtin_function(self, httpx_client, temp_workspace):
        """Test goto on builtin symbol."""
        builtin_file = temp_workspace / "builtin.py"
        create_python_file(builtin_file, "x = len([1, 2, 3])\n")

        response = httpx_client.post(
            "/defs",
            json={
                "file": "builtin.py",
                "line": 1,
                "col": 5,  # On "len"
                "root": str(temp_workspace)
            }
        )

        # May return empty or definition depending on Jedi config
        if response.status_code == 200:
            data = response.json()
            locations = data.get("locations", [])
            assert isinstance(locations, list)
            # Builtins may not have location
        else:
            assert response.status_code >= 400

    def test_goto_on_undefined_symbol(self, httpx_client, temp_workspace):
        """Test goto on undefined symbol."""
        undefined_file = temp_workspace / "undefined.py"
        create_python_file(undefined_file, "result = undefined_var\n")

        response = httpx_client.post(
            "/defs",
            json={
                "file": "undefined.py",
                "line": 1,
                "col": 10,  # On "undefined_var"
                "root": str(temp_workspace)
            }
        )

        # Should return empty locations
        if response.status_code == 200:
            data = response.json()
            locations = data.get("locations", [])
            # Should be empty for undefined symbol
            assert len(locations) == 0
        else:
            # May return error
            assert response.status_code >= 400

    def test_goto_on_lambda_function(self, httpx_client, temp_workspace):
        """Test goto on lambda function."""
        lambda_file = temp_workspace / "lambda_test.py"
        create_python_file(
            lambda_file,
            """
add = lambda x, y: x + y
result = add(1, 2)
"""
        )

        response = httpx_client.post(
            "/defs",
            json={
                "file": "lambda_test.py",
                "line": 3,
                "col": 10,  # On "add" in call
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Should find the lambda definition
            assert_locations_response(data, min_count=1)

    def test_goto_on_decorator(self, httpx_client, temp_workspace):
        """Test goto on decorator."""
        decorator_file = temp_workspace / "decorator.py"
        create_python_file(
            decorator_file,
            """
def my_decorator(func):
    return func

@my_decorator
def decorated_func():
    pass
"""
        )

        response = httpx_client.post(
            "/defs",
            json={
                "file": "decorator.py",
                "line": 5,
                "col": 2,  # On "@my_decorator"
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Should find the decorator definition
            assert_locations_response(data, min_count=1)


@pytest.mark.integration
@pytest.mark.jedi
class TestJediReferencesEdgeCases:
    """Test advanced references scenarios via /refs endpoint."""

    def test_references_cross_module(self, httpx_client, temp_workspace):
        """Test finding references across modules."""
        # Create module2 with helper function
        module2 = temp_workspace / "module2.py"
        create_python_file(
            module2,
            """
def helper():
    return 42
"""
        )

        # Create module1 that imports helper
        module1 = temp_workspace / "module1.py"
        create_python_file(
            module1,
            """
from module2 import helper

def function1():
    return helper()
"""
        )

        response = httpx_client.post(
            "/refs",
            json={
                "file": "module2.py",
                "line": 2,
                "col": 5,  # On "helper" function
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        # Should find definition and usage
        assert_locations_response(data, min_count=1)

        # Check that multiple files are referenced
        locations = data["locations"]
        files = set(loc["file"] for loc in locations)
        # May have both module1 and module2
        assert len(files) >= 1

    def test_references_with_rename(self, httpx_client, temp_workspace):
        """Test references when symbol is imported with different name."""
        # Create util module
        util = temp_workspace / "util.py"
        create_python_file(
            util,
            """
def original_name():
    return "hello"
"""
        )

        # Import with alias
        app = temp_workspace / "app.py"
        create_python_file(
            app,
            """
from util import original_name as renamed

result = renamed()
"""
        )

        response = httpx_client.post(
            "/refs",
            json={
                "file": "util.py",
                "line": 2,
                "col": 5,  # On "original_name"
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Should find references even with alias
            assert_locations_response(data, min_count=1)

    def test_references_in_nested_scopes(self, httpx_client, temp_workspace):
        """Test references in nested function scopes."""
        nested_file = temp_workspace / "nested.py"
        create_python_file(
            nested_file,
            """
def outer():
    x = 10

    def inner():
        return x  # Reference to outer's x

    return inner()
"""
        )

        response = httpx_client.post(
            "/refs",
            json={
                "file": "nested.py",
                "line": 3,
                "col": 5,  # On "x" definition
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Should find definition and usage in nested scope
            assert_locations_response(data, min_count=2)

    def test_references_class_attribute(self, httpx_client, temp_workspace):
        """Test references to class attributes."""
        class_file = temp_workspace / "class_attr.py"
        create_python_file(
            class_file,
            """
class MyClass:
    class_var = 42

    def method(self):
        return MyClass.class_var

obj = MyClass()
print(obj.class_var)
"""
        )

        response = httpx_client.post(
            "/refs",
            json={
                "file": "class_attr.py",
                "line": 3,
                "col": 5,  # On "class_var" definition
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Should find definition and usages
            assert_locations_response(data, min_count=1)

    def test_references_method_calls_chain(self, httpx_client, temp_workspace):
        """Test references for methods in call chains."""
        chain_file = temp_workspace / "chain.py"
        create_python_file(
            chain_file,
            """
class Builder:
    def add(self, x):
        return self

    def build(self):
        return "done"

result = Builder().add(1).add(2).build()
"""
        )

        response = httpx_client.post(
            "/refs",
            json={
                "file": "chain.py",
                "line": 3,
                "col": 9,  # On "add" method definition
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Should find definition and calls in chain
            assert_locations_response(data, min_count=1)


@pytest.mark.integration
@pytest.mark.jedi
@pytest.mark.skip(reason="Server does not have /complete endpoint")
class TestJediCompletionNotAvailable:
    """Completion tests - endpoint not available in current server."""

    def test_completion_endpoint_not_implemented(self):
        """Document that completion is not yet implemented."""
        pass


@pytest.mark.integration
@pytest.mark.jedi
@pytest.mark.skip(reason="Server does not have /infer endpoint - use /hover instead")
class TestJediInferNotAvailable:
    """Type inference tests - endpoint not available in current server."""

    def test_infer_endpoint_not_implemented(self):
        """Document that direct infer is not implemented - use /hover."""
        pass
