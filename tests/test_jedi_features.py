"""Tests for Jedi-based features (goto, infer, refs, hover)."""

import json
import pathlib
import sys
from io import StringIO

import pytest

# Add parent directory to path to import pyclide
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pyclide import jedi_script, jedi_to_locations


class TestJediFeatures:
    """Test Jedi integration features."""

    @pytest.fixture
    def fixtures_dir(self):
        """Return the fixtures directory path."""
        return pathlib.Path(__file__).parent / "fixtures"

    def test_jedi_goto_function_definition(self, fixtures_dir):
        """Test goto for function definition."""
        # In sample_usage.py, line 9 has "hello_world" - should go to its definition
        scr = jedi_script(fixtures_dir, "sample_usage.py")
        # Line 9, column 20 is on "hello_world" in the function call
        results = scr.goto(9, 20)

        assert len(results) > 0
        locations = jedi_to_locations(results)
        assert len(locations) > 0

        # Jedi may point to the import statement in sample_usage.py or the definition in sample_module.py
        # Both are valid behaviors
        assert locations[0]["name"] == "hello_world"
        assert "sample_usage.py" in locations[0]["path"] or "sample_module.py" in locations[0]["path"]

    def test_jedi_goto_class_definition(self, fixtures_dir):
        """Test goto for class definition."""
        scr = jedi_script(fixtures_dir, "sample_usage.py")
        # Line 13, column 15 is on "Calculator" in the class instantiation
        results = scr.goto(13, 15)

        assert len(results) > 0
        locations = jedi_to_locations(results)
        assert len(locations) > 0

        # Jedi may point to the import statement or the class definition
        # Both are valid behaviors
        assert locations[0]["name"] == "Calculator"
        assert "sample_usage.py" in locations[0]["path"] or "sample_module.py" in locations[0]["path"]

    def test_jedi_infer_variable_type(self, fixtures_dir):
        """Test type inference for variables."""
        scr = jedi_script(fixtures_dir, "sample_usage.py")
        # Line 9, column 5 is on "greeting" variable
        results = scr.infer(9, 5)

        assert len(results) > 0
        # Should infer that greeting is a str
        assert results[0].type == "instance"

    def test_jedi_get_references(self, fixtures_dir):
        """Test finding references to a function."""
        scr = jedi_script(fixtures_dir, "sample_module.py")
        # Line 4, column 5 is on the "hello_world" function definition
        results = scr.get_references(4, 5)

        locations = jedi_to_locations(results)
        assert len(locations) >= 2  # At least definition + 1 usage

        # Should include both definition and usage
        paths = [loc["path"] for loc in locations]
        assert any("sample_module.py" in p for p in paths)
        assert any("sample_usage.py" in p for p in paths)

    def test_jedi_hover_function(self, fixtures_dir):
        """Test hover information for a function."""
        scr = jedi_script(fixtures_dir, "sample_module.py")
        # Line 4, column 5 is on "hello_world"
        names = scr.infer(4, 5)

        assert len(names) > 0
        name = names[0]

        # Check basic properties
        assert name.name == "hello_world"
        assert name.type == "function"

        # Check docstring is available
        docstring = name.docstring()
        assert "greeting message" in docstring.lower()

    def test_jedi_hover_class_method(self, fixtures_dir):
        """Test hover information for a class method."""
        scr = jedi_script(fixtures_dir, "sample_module.py")
        # Line 30, column 9 is on "add" method
        names = scr.infer(30, 9)

        assert len(names) > 0
        name = names[0]

        assert name.name == "add"
        assert name.type == "function"

        # Check signature
        sigs = name.get_signatures()
        assert len(sigs) > 0

    def test_jedi_complete(self, fixtures_dir):
        """Test code completion."""
        scr = jedi_script(fixtures_dir, "sample_usage.py")
        # After "my_calc." we should get completions for Calculator methods
        # This would be at a position after creating my_calc
        # We can test completion on sample_module instead
        scr2 = jedi_script(fixtures_dir, "sample_module.py")

        # At the end of the file, test "calc." completion (line 56 after "calc.")
        completions = scr2.complete(56, 5)  # After "calc."

        # Should have add, multiply, get_value methods
        completion_names = [c.name for c in completions]
        assert "add" in completion_names
        assert "multiply" in completion_names
        assert "get_value" in completion_names
