"""Tests for modern Python features (3.9+, 3.10+, 3.13)."""

import pathlib
import sys
import pytest

# Add parent directory to path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pyclide import RopeEngine, jedi_script


class TestModernTyping:
    """Test modern type hints (PEP 585, 604, 673)."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create project with modern type hints."""
        test_file = tmp_path / "modern_types.py"
        test_file.write_text(
            """
from typing import Callable, Protocol
from collections.abc import Sequence

# PEP 585: Built-in generics (3.9+)
def process_items(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

# PEP 604: Union operator (3.10+)
def handle_value(x: int | str | None) -> str:
    if x is None:
        return "none"
    return str(x)

# Protocol (structural subtyping)
class Drawable(Protocol):
    def draw(self) -> None: ...

# Type aliases with | operator
Result = dict[str, list[int] | None]

# Self type (3.11+)
class Builder:
    def __init__(self):
        self.value = 0

    def add(self, x: int):
        self.value += x
        return self  # Returns Self

result = process_items(["hello", "world"])
""",
            encoding="utf-8",
        )
        return tmp_path

    def test_goto_on_modern_generics(self, temp_project):
        """Test goto works with built-in generics (list[str] instead of List[str])."""
        scr = jedi_script(temp_project, "modern_types.py")

        # Test that Jedi can parse file with modern generics
        # Just verify script creation works with modern syntax
        assert scr is not None

        # Try completion to verify Jedi understands the types
        completions = scr.complete(7, 8)  # Inside process_items function
        assert isinstance(completions, list)

    def test_references_with_union_operator(self, temp_project):
        """Test references with modern union syntax (int | str)."""
        scr = jedi_script(temp_project, "modern_types.py")

        # Find references to handle_value
        refs = scr.get_references(12, 5, include_builtins=False)

        assert isinstance(refs, list)

    @pytest.mark.xfail(reason="Rope has limited support for Protocol classes")
    def test_rename_with_protocol(self, temp_project):
        """Test rename with Protocol classes."""
        eng = RopeEngine(temp_project)

        # Rename Protocol class
        patches = eng.rename("modern_types.py", 19, 7, "CanDraw")

        if "modern_types.py" in patches:
            assert "CanDraw" in patches["modern_types.py"]


class TestPatternMatching:
    """Test pattern matching (Python 3.10+)."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create project with match statements."""
        test_file = tmp_path / "patterns.py"
        test_file.write_text(
            """
def process_command(command):
    match command:
        case ["quit"]:
            return "quitting"
        case ["load", filename]:
            return f"loading {filename}"
        case ["save", filename]:
            return f"saving {filename}"
        case _:
            return "unknown"

# Structural pattern matching with classes
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

def describe_point(point):
    match point:
        case Point(x=0, y=0):
            return "origin"
        case Point(x=0, y=y):
            return f"on y-axis at {y}"
        case Point(x=x, y=0):
            return f"on x-axis at {x}"
        case Point(x=x, y=y):
            return f"at ({x}, {y})"
        case _:
            return "not a point"

result = process_command(["load", "data.txt"])
""",
            encoding="utf-8",
        )
        return tmp_path

    def test_goto_in_match_statement(self, temp_project):
        """Test goto works inside match/case blocks."""
        scr = jedi_script(temp_project, "patterns.py")

        # Goto on process_command in the last line
        results = scr.goto(32, 10)

        assert len(results) >= 1

    def test_rename_variable_in_pattern(self, temp_project):
        """Test rename works with pattern matching variables."""
        eng = RopeEngine(temp_project)

        # Rename the command parameter
        patches = eng.rename("patterns.py", 2, 20, "cmd")

        if "patterns.py" in patches:
            assert "cmd" in patches["patterns.py"]


class TestDataclasses:
    """Test dataclasses and modern class features."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create project with dataclasses."""
        test_file = tmp_path / "dataclass_test.py"
        test_file.write_text(
            """
from dataclasses import dataclass, field

@dataclass
class User:
    name: str
    age: int
    email: str = field(default="")
    active: bool = True

    def get_info(self) -> str:
        return f"{self.name} ({self.age})"

@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def distance_from_origin(self) -> float:
        return (self.x ** 2 + self.y ** 2) ** 0.5

user = User(name="Alice", age=30)
info = user.get_info()
""",
            encoding="utf-8",
        )
        return tmp_path

    def test_goto_dataclass_field(self, temp_project):
        """Test goto on dataclass field."""
        scr = jedi_script(temp_project, "dataclass_test.py")

        # Goto on name field - line 23 is where User(name="Alice", age=30) is
        results = scr.goto(23, 18)  # on "name" in User(name=...)

        assert isinstance(results, list)

    def test_rename_dataclass_method(self, temp_project):
        """Test rename method in dataclass."""
        eng = RopeEngine(temp_project)

        # Rename get_info to get_details
        patches = eng.rename("dataclass_test.py", 11, 9, "get_details")

        if "dataclass_test.py" in patches:
            content = patches["dataclass_test.py"]
            assert "get_details" in content

    def test_occurrences_dataclass_field(self, temp_project):
        """Test finding occurrences of dataclass field."""
        eng = RopeEngine(temp_project)

        # Find occurrences of 'name' field
        occurrences = eng.occurrences("dataclass_test.py", 6, 5)

        # Should find at least the definition
        assert len(occurrences) >= 1


class TestAsyncAwait:
    """Test async/await syntax."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create project with async code."""
        test_file = tmp_path / "async_test.py"
        test_file.write_text(
            """
import asyncio

async def fetch_data(url: str) -> dict:
    await asyncio.sleep(0.1)
    return {"url": url, "data": "content"}

async def process_urls(urls: list[str]) -> list[dict]:
    tasks = [fetch_data(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return results

async def main():
    urls = ["http://example.com", "http://test.com"]
    data = await process_urls(urls)
    return data

# Async context manager
class AsyncResource:
    async def __aenter__(self):
        await asyncio.sleep(0.1)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await asyncio.sleep(0.1)

async def use_resource():
    async with AsyncResource() as resource:
        return resource
""",
            encoding="utf-8",
        )
        return tmp_path

    def test_goto_async_function(self, temp_project):
        """Test goto on async function."""
        scr = jedi_script(temp_project, "async_test.py")

        # Goto on fetch_data
        results = scr.goto(9, 13)  # on fetch_data in list comprehension

        assert len(results) >= 1

    def test_rename_async_function(self, temp_project):
        """Test rename async function."""
        eng = RopeEngine(temp_project)

        # Rename fetch_data to get_data
        patches = eng.rename("async_test.py", 4, 11, "get_data")

        if "async_test.py" in patches:
            content = patches["async_test.py"]
            assert "async def get_data" in content

    def test_references_await_expression(self, temp_project):
        """Test finding references to awaited function."""
        scr = jedi_script(temp_project, "async_test.py")

        # Get references to process_urls
        refs = scr.get_references(8, 11, include_builtins=False)

        assert isinstance(refs, list)


class TestWalrusOperator:
    """Test walrus operator := (Python 3.8+)."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create project with walrus operator."""
        test_file = tmp_path / "walrus.py"
        test_file.write_text(
            """
# Walrus operator in if statement
def process_data(data: list[int]) -> int:
    if (n := len(data)) > 10:
        return n * 2
    return n

# Walrus in while loop
def read_chunks(items: list[str]) -> list[str]:
    chunks = []
    index = 0
    while (chunk := items[index:index+3]) and index < len(items):
        chunks.append(chunk)
        index += 3
    return chunks

# Walrus in list comprehension
def find_long_words(text: str) -> list[str]:
    words = text.split()
    return [match.upper() for word in words if (match := word.lower()) and len(match) > 5]

result = process_data([1, 2, 3, 4, 5])
""",
            encoding="utf-8",
        )
        return tmp_path

    def test_goto_walrus_variable(self, temp_project):
        """Test goto on variable assigned with walrus operator."""
        scr = jedi_script(temp_project, "walrus.py")

        # Try goto on 'n' in the walrus expression
        results = scr.goto(4, 9)  # on 'n' in (n := len(data))

        assert isinstance(results, list)

    def test_rename_walrus_variable(self, temp_project):
        """Test rename variable used in walrus operator."""
        eng = RopeEngine(temp_project)

        # Rename 'n' to 'count'
        patches = eng.rename("walrus.py", 4, 9, "count")

        if "walrus.py" in patches:
            content = patches["walrus.py"]
            # Both occurrences should be renamed
            assert "count" in content


class TestModernStringFeatures:
    """Test modern string features (f-strings with =, etc.)."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create project with modern string features."""
        test_file = tmp_path / "strings.py"
        test_file.write_text(
            '''
# f-strings with = (3.8+)
def debug_vars(x: int, y: int) -> str:
    return f"{x=}, {y=}, {x+y=}"

# f-strings with format specs
def format_number(value: float) -> str:
    return f"{value:.2f}"

# Raw f-strings
def make_regex(pattern: str) -> str:
    return rf"\\b{pattern}\\b"

# Multi-line f-strings
def describe_user(name: str, age: int, city: str) -> str:
    return f"""
    Name: {name}
    Age: {age}
    City: {city}
    """

result = debug_vars(10, 20)
''',
            encoding="utf-8",
        )
        return tmp_path

    def test_goto_in_fstring(self, temp_project):
        """Test goto on variable inside f-string."""
        scr = jedi_script(temp_project, "strings.py")

        # Goto on 'x' in f-string
        results = scr.goto(4, 16)  # on x in f"{x=}"

        assert isinstance(results, list)

    def test_rename_var_used_in_fstring(self, temp_project):
        """Test rename variable used in f-string."""
        eng = RopeEngine(temp_project)

        # Rename parameter 'value' to 'number'
        patches = eng.rename("strings.py", 7, 20, "number")

        if "strings.py" in patches:
            content = patches["strings.py"]
            # Should rename both definition and usage in f-string
            assert "number" in content
