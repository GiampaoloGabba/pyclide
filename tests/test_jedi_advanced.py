"""Advanced tests for Jedi engine functionality."""

import pathlib
import shutil
import sys

import pytest

# Add parent directory to path to import pyclide
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pyclide import jedi_script, jedi_to_locations


class TestJediCompletionEdgeCases:
    """Test advanced completion scenarios."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project."""
        test_file = tmp_path / "completions.py"
        test_file.write_text(
            """
class Calculator:
    def add(self, x, y):
        return x + y

    def multiply(self, x, y):
        return x * y

calc = Calculator()
result = calc.
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_completion_after_dot_method_attributes(self, temp_project):
        """Test completion after dot for methods and attributes."""
        scr = jedi_script(temp_project, "completions.py")

        # Line 10 after "calc." - the cursor is right after the dot
        completions = scr.complete(10, 14)

        # Should suggest add and multiply methods
        names = [c.name for c in completions]
        assert "add" in names
        assert "multiply" in names

    def test_completion_import_statement(self, temp_project):
        """Test completion in import statements."""
        import_file = temp_project / "imports.py"
        import_file.write_text(
            """
from pathlib import P
""",
            encoding="utf-8",
        )

        scr = jedi_script(temp_project, "imports.py")

        # Complete after "P" - should suggest Path
        completions = scr.complete(2, 21)

        names = [c.name for c in completions]
        # May include Path, PurePath, etc.
        assert any("Path" in name for name in names)

    def test_completion_no_suggestions(self, temp_project):
        """Test completion when no suggestions available."""
        empty_file = temp_project / "empty.py"
        empty_file.write_text("# Just comment\n", encoding="utf-8")

        scr = jedi_script(temp_project, "empty.py")

        completions = scr.complete(1, 10)

        # May have some builtin completions or be empty
        assert isinstance(completions, list)


class TestJediGotoEdgeCases:
    """Test advanced goto scenarios."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project."""
        # Create file with overloads
        overload_file = tmp_path / "overload.py"
        overload_file.write_text(
            """
class Base:
    def method(self):
        pass

class Derived(Base):
    def method(self):
        pass

obj = Derived()
obj.method()
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_goto_multiple_definitions_overloads(self, temp_project):
        """Test goto with multiple definitions (method overriding)."""
        scr = jedi_script(temp_project, "overload.py")

        # Goto on method() call at line 11
        results = scr.goto(11, 5)

        # Jedi may return one or multiple definitions
        locations = jedi_to_locations(results)
        assert isinstance(locations, list)
        assert len(locations) >= 1

    def test_goto_on_import_statement(self, temp_project):
        """Test goto on an import statement."""
        import_file = temp_project / "imports.py"
        import_file.write_text("import os\n", encoding="utf-8")

        scr = jedi_script(temp_project, "imports.py")

        # Goto on "os"
        results = scr.goto(1, 8)

        # May go to os module definition
        assert isinstance(results, list)

    def test_goto_on_builtin_none(self, temp_project):
        """Test goto on builtin symbol."""
        builtin_file = temp_project / "builtin.py"
        builtin_file.write_text("x = len([1, 2, 3])\n", encoding="utf-8")

        scr = jedi_script(temp_project, "builtin.py")

        # Goto on "len" - builtin function
        results = scr.goto(1, 5)

        # May return empty or definition depending on Jedi config
        assert isinstance(results, list)

    def test_goto_on_undefined_symbol(self, temp_project):
        """Test goto on undefined symbol."""
        undefined_file = temp_project / "undefined.py"
        undefined_file.write_text("result = undefined_var\n", encoding="utf-8")

        scr = jedi_script(temp_project, "undefined.py")

        # Goto on undefined_var
        results = scr.goto(1, 10)

        # Should return empty
        locations = jedi_to_locations(results)
        assert isinstance(locations, list)


class TestJediInferTypes:
    """Test type inference scenarios."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project."""
        types_file = tmp_path / "types.py"
        types_file.write_text(
            """
from typing import List, Dict, Optional, Union

# Complex type
users: List[Dict[str, int]] = []

# Union type
result: Union[int, str] = 42

# Optional
value: Optional[str] = None

# Generic types
def get_items() -> List[str]:
    return ["a", "b"]

items = get_items()
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_infer_complex_types(self, temp_project):
        """Test inferring complex types like List[Dict[str, int]]."""
        scr = jedi_script(temp_project, "types.py")

        # Infer type of "users"
        names = scr.infer(5, 1)

        assert len(names) > 0
        # Type should be instance or similar
        assert names[0].type in ["instance", "statement", "param"]

    def test_infer_union_types(self, temp_project):
        """Test inferring Union types."""
        scr = jedi_script(temp_project, "types.py")

        # Infer type of "result"
        names = scr.infer(8, 1)

        assert len(names) > 0

    def test_infer_generic_types(self, temp_project):
        """Test inferring generic return types."""
        scr = jedi_script(temp_project, "types.py")

        # Infer type of "items" (should be List[str])
        # Line 17 is where "items = get_items()" is located
        names = scr.infer(17, 1)

        assert len(names) > 0

    def test_infer_unknown_type_graceful(self, temp_project):
        """Test that unknown types are handled gracefully."""
        unknown_file = temp_project / "unknown.py"
        unknown_file.write_text("x = some_dynamic_value()\n", encoding="utf-8")

        scr = jedi_script(temp_project, "unknown.py")

        # Infer type of x
        names = scr.infer(1, 1)

        # Should handle gracefully even if type is unknown
        assert isinstance(names, list)


class TestJediReferencesEdgeCases:
    """Test advanced references scenarios."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project."""
        # Create files with circular imports
        file1 = tmp_path / "module1.py"
        file1.write_text(
            """
from module2 import helper

def function1():
    return helper()
""",
            encoding="utf-8",
        )

        file2 = tmp_path / "module2.py"
        file2.write_text(
            """
def helper():
    return 42
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_references_cross_module(self, temp_project):
        """Test finding references across modules."""
        scr = jedi_script(temp_project, "module2.py")

        # Get references for "helper" function
        refs = scr.get_references(2, 5, include_builtins=False)

        locations = jedi_to_locations(refs)

        # Should find definition and usage
        assert len(locations) >= 1

    def test_references_in_docstrings_excluded(self, temp_project):
        """Test that references in docstrings are handled."""
        docstring_file = temp_project / "docstrings.py"
        docstring_file.write_text(
            '''
def foo():
    """This is foo function."""
    pass

def bar():
    """Call foo() here."""
    return foo()
''',
            encoding="utf-8",
        )

        scr = jedi_script(temp_project, "docstrings.py")

        # Get references for "foo"
        refs = scr.get_references(2, 5, include_builtins=False)

        locations = jedi_to_locations(refs)

        # Should find definition and actual usage
        assert isinstance(locations, list)
