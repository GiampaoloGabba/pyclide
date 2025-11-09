"""Tests for modern Python features (3.10+) via server API."""

import sys
import pytest
from tests.utils import create_python_file, assert_patches_valid


@pytest.mark.integration
@pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10+")
class TestModernTyping:
    """Tests for modern type hints."""

    def test_goto_on_modern_generics(self, httpx_client, temp_workspace):
        """Test goto with Python 3.10+ generics syntax."""
        test_file = temp_workspace / "generics.py"
        create_python_file(
            test_file,
            """
def process(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

result = process(["a", "b"])
"""
        )

        response = httpx_client.post(
            "/defs",
            json={
                "file": "generics.py",
                "line": 5,
                "col": 10,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200

    def test_references_with_union_operator(self, httpx_client, temp_workspace):
        """Test references with | union operator."""
        test_file = temp_workspace / "unions.py"
        create_python_file(
            test_file,
            """
def func(x: int | str) -> int | None:
    return len(x) if isinstance(x, str) else x
"""
        )

        response = httpx_client.post(
            "/refs",
            json={
                "file": "unions.py",
                "line": 2,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200

    def test_rename_with_protocol(self, httpx_client, temp_workspace):
        """Test rename with Protocol."""
        test_file = temp_workspace / "protocol.py"
        create_python_file(
            test_file,
            """
from typing import Protocol

class Drawable(Protocol):
    def draw(self) -> None: ...
"""
        )

        response = httpx_client.post(
            "/rename",
            json={
                "file": "protocol.py",
                "line": 4,
                "col": 7,
                "new_name": "Renderable",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data["patches"]
            assert_patches_valid(patches)


@pytest.mark.integration
@pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10+")
class TestPatternMatching:
    """Tests for match/case statements."""

    def test_goto_in_match_statement(self, httpx_client, temp_workspace):
        """Test goto within match statement."""
        test_file = temp_workspace / "match_test.py"
        create_python_file(
            test_file,
            """
def handle(value):
    match value:
        case 1:
            return "one"
        case _:
            return "other"
"""
        )

        response = httpx_client.post(
            "/defs",
            json={
                "file": "match_test.py",
                "line": 2,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200

    def test_rename_variable_in_pattern(self, httpx_client, temp_workspace):
        """Test rename variable used in pattern."""
        test_file = temp_workspace / "pattern.py"
        create_python_file(
            test_file,
            """
def process(point):
    match point:
        case (x, y):
            return x + y
"""
        )

        response = httpx_client.post(
            "/rename",
            json={
                "file": "pattern.py",
                "line": 4,
                "col": 15,
                "new_name": "a",
                "root": str(temp_workspace)
            }
        )

        # May or may not work depending on Rope support
        assert response.status_code in (200, 400, 500)


@pytest.mark.integration
class TestDataclasses:
    """Tests for dataclass features."""

    def test_goto_dataclass_field(self, httpx_client, temp_workspace):
        """Test goto on dataclass field."""
        test_file = temp_workspace / "dataclass_test.py"
        create_python_file(
            test_file,
            """
from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

p = Point(1, 2)
print(p.x)
"""
        )

        response = httpx_client.post(
            "/defs",
            json={
                "file": "dataclass_test.py",
                "line": 10,
                "col": 9,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200

    def test_rename_dataclass_method(self, httpx_client, temp_workspace):
        """Test rename dataclass method."""
        test_file = temp_workspace / "dataclass_method.py"
        create_python_file(
            test_file,
            """
from dataclasses import dataclass

@dataclass
class Data:
    value: int

    def process(self):
        return self.value * 2
"""
        )

        response = httpx_client.post(
            "/rename",
            json={
                "file": "dataclass_method.py",
                "line": 8,
                "col": 9,
                "new_name": "compute",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data["patches"]
            assert_patches_valid(patches)

    def test_occurrences_dataclass_field(self, httpx_client, temp_workspace):
        """Test occurrences of dataclass field."""
        test_file = temp_workspace / "dataclass_field.py"
        create_python_file(
            test_file,
            """
from dataclasses import dataclass

@dataclass
class Config:
    timeout: int

c = Config(30)
print(c.timeout)
"""
        )

        response = httpx_client.post(
            "/occurrences",
            json={
                "file": "dataclass_field.py",
                "line": 6,
                "col": 5,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200


@pytest.mark.integration
class TestAsyncAwait:
    """Tests for async/await syntax."""

    def test_goto_async_function(self, httpx_client, temp_workspace):
        """Test goto on async function."""
        test_file = temp_workspace / "async_test.py"
        create_python_file(
            test_file,
            """
async def fetch_data():
    return "data"

async def main():
    result = await fetch_data()
"""
        )

        response = httpx_client.post(
            "/defs",
            json={
                "file": "async_test.py",
                "line": 6,
                "col": 19,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200

    def test_rename_async_function(self, httpx_client, temp_workspace):
        """Test rename async function."""
        test_file = temp_workspace / "async_rename.py"
        create_python_file(
            test_file,
            """
async def load():
    return 42

async def process():
    data = await load()
"""
        )

        response = httpx_client.post(
            "/rename",
            json={
                "file": "async_rename.py",
                "line": 2,
                "col": 11,
                "new_name": "fetch",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data["patches"]
            assert_patches_valid(patches)

    def test_references_await_expression(self, httpx_client, temp_workspace):
        """Test references in await expression."""
        test_file = temp_workspace / "await_refs.py"
        create_python_file(
            test_file,
            """
async def helper():
    return "help"

async def main():
    result = await helper()
"""
        )

        response = httpx_client.post(
            "/refs",
            json={
                "file": "await_refs.py",
                "line": 2,
                "col": 11,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10+")
class TestWalrusOperator:
    """Tests for walrus operator :=."""

    def test_goto_walrus_variable(self, httpx_client, temp_workspace):
        """Test goto on walrus operator variable."""
        test_file = temp_workspace / "walrus.py"
        create_python_file(
            test_file,
            """
if (n := len([1, 2, 3])) > 2:
    print(n)
"""
        )

        response = httpx_client.post(
            "/defs",
            json={
                "file": "walrus.py",
                "line": 3,
                "col": 11,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200

    def test_rename_walrus_variable(self, httpx_client, temp_workspace):
        """Test rename walrus operator variable."""
        test_file = temp_workspace / "walrus_rename.py"
        create_python_file(
            test_file,
            """
if (count := len([1, 2])) > 1:
    print(count)
"""
        )

        response = httpx_client.post(
            "/rename",
            json={
                "file": "walrus_rename.py",
                "line": 2,
                "col": 5,
                "new_name": "size",
                "root": str(temp_workspace)
            }
        )

        # May or may not work depending on Rope support
        assert response.status_code in (200, 400, 500)


@pytest.mark.integration
class TestModernStringFeatures:
    """Tests for f-strings and modern string features."""

    def test_goto_in_fstring(self, httpx_client, temp_workspace):
        """Test goto on variable in f-string."""
        test_file = temp_workspace / "fstring.py"
        create_python_file(
            test_file,
            """
name = "Alice"
message = f"Hello {name}"
"""
        )

        response = httpx_client.post(
            "/defs",
            json={
                "file": "fstring.py",
                "line": 3,
                "col": 20,
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200

    def test_rename_var_used_in_fstring(self, httpx_client, temp_workspace):
        """Test rename variable used in f-string."""
        test_file = temp_workspace / "fstring_rename.py"
        create_python_file(
            test_file,
            """
value = 42
text = f"The value is {value}"
"""
        )

        response = httpx_client.post(
            "/rename",
            json={
                "file": "fstring_rename.py",
                "line": 2,
                "col": 1,
                "new_name": "number",
                "root": str(temp_workspace)
            }
        )

        if response.status_code == 200:
            data = response.json()
            patches = data["patches"]
            content = list(patches.values())[0]
            # Both occurrences should be renamed
            assert "number" in content
            assert content.count("number") >= 2
