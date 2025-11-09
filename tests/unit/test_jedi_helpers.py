"""Unit tests for Jedi helper functions."""

import tempfile
from pathlib import Path

import pytest

from pyclide_server.jedi_helpers import jedi_to_locations, jedi_script


@pytest.mark.unit
@pytest.mark.jedi
class TestJediHelpers:
    """Test Jedi helper functions in isolation."""

    def test_jedi_to_locations_valid(self):
        """jedi_to_locations converts definitions correctly."""
        # Create a simple test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def hello():\n    pass\n")
            test_file = Path(f.name)

        try:
            import jedi
            script = jedi.Script(path=str(test_file))
            # Get definitions for 'hello'
            results = script.goto(1, 4)  # On 'def hello'

            locations = jedi_to_locations(results)

            # Should have at least one result
            assert len(locations) > 0

            # Check structure
            loc = locations[0]
            assert "path" in loc
            assert "line" in loc
            assert "column" in loc
            assert loc["line"] > 0
            assert loc["column"] >= 0

        finally:
            test_file.unlink()

    def test_jedi_to_locations_empty(self):
        """jedi_to_locations handles empty results."""
        locations = jedi_to_locations([])
        assert locations == []
        assert isinstance(locations, list)

    def test_jedi_to_locations_no_module_path(self):
        """jedi_to_locations filters out results without module_path."""
        # Mock objects without module_path
        class MockName:
            def __init__(self, has_path):
                self.name = "test"
                self.line = 1
                self.column = 0
                self.type = "function"
                if has_path:
                    self.module_path = "/path/to/file.py"
                else:
                    self.module_path = None

        mock_results = [
            MockName(True),   # Has module_path
            MockName(False),  # No module_path
            MockName(True),   # Has module_path
        ]

        locations = jedi_to_locations(mock_results)

        # Should filter out the one without module_path
        assert len(locations) == 2

        # All results should have valid paths
        for loc in locations:
            assert loc["path"] is not None
            assert len(loc["path"]) > 0

    def test_jedi_to_locations_structure(self):
        """jedi_to_locations creates correct structure."""
        # Create a test file with a simple function
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def test_func():\n    return 42\n")
            test_file = Path(f.name)

        try:
            import jedi
            script = jedi.Script(path=str(test_file))
            results = script.goto(1, 4)  # On 'def test_func'

            locations = jedi_to_locations(results)

            if len(locations) > 0:
                loc = locations[0]

                # Check all required keys
                assert "path" in loc
                assert "line" in loc
                assert "column" in loc

                # Check types
                assert isinstance(loc["path"], str)
                assert isinstance(loc["line"], int)
                assert isinstance(loc["column"], int)

                # Check values are reasonable
                assert loc["line"] > 0
                assert loc["column"] >= 0

        finally:
            test_file.unlink()

    def test_jedi_to_locations_with_builtin(self):
        """jedi_to_locations handles builtin definitions gracefully."""
        # Create a script that references a builtin
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("x = len([1, 2, 3])\n")
            test_file = Path(f.name)

        try:
            import jedi
            script = jedi.Script(path=str(test_file))
            # Try to goto definition of 'len' (builtin)
            results = script.goto(1, 5)

            # This should not crash
            locations = jedi_to_locations(results)

            # Results depend on Jedi version, but should be a list
            assert isinstance(locations, list)

        finally:
            test_file.unlink()


@pytest.mark.unit
@pytest.mark.jedi
class TestJediScript:
    """Test jedi_script() function with all edge cases."""

    def test_jedi_script_valid_file(self, tmp_path):
        """jedi_script creates Script for valid file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        import jedi
        script = jedi_script(tmp_path, "test.py")

        assert script is not None
        assert isinstance(script, jedi.Script)

    def test_jedi_script_with_relative_path(self, tmp_path):
        """jedi_script handles relative path correctly."""
        subdir = tmp_path / "src"
        subdir.mkdir()
        test_file = subdir / "module.py"
        test_file.write_text("x = 1\n")

        script = jedi_script(tmp_path, "src/module.py")

        assert script is not None

    def test_jedi_script_with_absolute_path(self, tmp_path):
        """jedi_script handles absolute path correctly."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        # Pass absolute path as file_path
        script = jedi_script(tmp_path, str(test_file))

        assert script is not None

    def test_jedi_script_nonexistent_file(self, tmp_path):
        """jedi_script handles non-existent file."""
        # Jedi raises FileNotFoundError for non-existent files
        with pytest.raises(FileNotFoundError):
            script = jedi_script(tmp_path, "nonexistent.py")

    def test_jedi_script_with_syntax_error(self, tmp_path):
        """jedi_script handles file with syntax error."""
        test_file = tmp_path / "bad.py"
        test_file.write_text("def broken(\n")  # Syntax error

        # Jedi should still create Script
        script = jedi_script(tmp_path, "bad.py")

        assert script is not None
        # Script is created, but completions/goto might fail

    def test_jedi_script_empty_file(self, tmp_path):
        """jedi_script handles empty file."""
        test_file = tmp_path / "empty.py"
        test_file.write_text("")

        script = jedi_script(tmp_path, "empty.py")

        assert script is not None

    def test_jedi_script_with_unicode(self, tmp_path):
        """jedi_script handles file with unicode content."""
        test_file = tmp_path / "unicode.py"
        test_file.write_text("# Привет мир\ndef hello():\n    return '你好'\n")

        script = jedi_script(tmp_path, "unicode.py")

        assert script is not None

    def test_jedi_script_path_resolution(self, tmp_path):
        """jedi_script resolves path correctly."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        script = jedi_script(tmp_path, "test.py")

        # Script should have correct path
        assert script is not None
        # script.path can be string or Path, convert to string
        assert str(script.path).endswith("test.py")

    def test_jedi_script_with_dots_in_path(self, tmp_path):
        """jedi_script handles path with .. correctly."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        # Use relative path with ..
        script = jedi_script(subdir, "../test.py")

        assert script is not None

    def test_jedi_script_returns_jedi_script_type(self, tmp_path):
        """jedi_script always returns jedi.Script instance."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def func():\n    pass\n")

        import jedi
        script = jedi_script(tmp_path, "test.py")

        assert isinstance(script, jedi.Script)


@pytest.mark.unit
@pytest.mark.jedi
class TestJediToLocationsExtended:
    """Extended tests for jedi_to_locations() edge cases."""

    def test_jedi_to_locations_with_none_column(self):
        """jedi_to_locations handles results with column=None."""
        class MockName:
            def __init__(self):
                self.name = "test"
                self.line = 5
                self.column = None  # None column
                self.type = "function"
                self.module_path = "/path/to/file.py"

        results = [MockName()]
        locations = jedi_to_locations(results)

        assert len(locations) == 1
        # Should default column to 1
        assert locations[0]["column"] == 1

    def test_jedi_to_locations_with_none_name(self):
        """jedi_to_locations handles results with name=None."""
        class MockName:
            def __init__(self):
                self.name = None
                self.line = 5
                self.column = 10
                self.type = "module"
                self.module_path = "/path/to/file.py"

        results = [MockName()]
        locations = jedi_to_locations(results)

        assert len(locations) == 1
        assert locations[0]["name"] is None

    def test_jedi_to_locations_with_none_type(self):
        """jedi_to_locations handles results with type=None."""
        class MockName:
            def __init__(self):
                self.name = "test"
                self.line = 5
                self.column = 10
                self.type = None
                self.module_path = "/path/to/file.py"

        results = [MockName()]
        locations = jedi_to_locations(results)

        assert len(locations) == 1
        assert locations[0]["type"] is None

    def test_jedi_to_locations_mixed_valid_invalid(self):
        """jedi_to_locations filters mixed valid and invalid results."""
        class ValidName:
            def __init__(self):
                self.name = "valid"
                self.line = 5
                self.column = 10
                self.type = "function"
                self.module_path = "/path/to/file.py"

        class InvalidName:
            def __init__(self):
                self.name = "invalid"
                self.line = None  # Invalid: None line
                self.column = 10
                self.type = "function"
                self.module_path = "/path/to/file.py"

        class NoPathName:
            def __init__(self):
                self.name = "no_path"
                self.line = 5
                self.column = 10
                self.type = "function"
                self.module_path = None  # Invalid: None module_path

        results = [ValidName(), InvalidName(), NoPathName(), ValidName()]
        locations = jedi_to_locations(results)

        # Should only include the 2 valid ones
        assert len(locations) == 2

    def test_jedi_to_locations_all_fields_present(self):
        """jedi_to_locations includes all expected fields."""
        class MockName:
            def __init__(self):
                self.name = "test_function"
                self.line = 42
                self.column = 8
                self.type = "function"
                self.module_path = "/home/user/project/module.py"

        results = [MockName()]
        locations = jedi_to_locations(results)

        assert len(locations) == 1
        loc = locations[0]

        # Check all fields
        assert "path" in loc
        assert "line" in loc
        assert "column" in loc
        assert "name" in loc
        assert "type" in loc

        # Check values
        assert loc["path"] == "/home/user/project/module.py"
        assert loc["line"] == 42
        assert loc["column"] == 8
        assert loc["name"] == "test_function"
        assert loc["type"] == "function"

    def test_jedi_to_locations_column_zero(self):
        """jedi_to_locations handles column=0."""
        class MockName:
            def __init__(self):
                self.name = "test"
                self.line = 1
                self.column = 0  # Zero column
                self.type = "variable"
                self.module_path = "/path/to/file.py"

        results = [MockName()]
        locations = jedi_to_locations(results)

        assert len(locations) == 1
        # Should use column or default to 1
        assert locations[0]["column"] in [0, 1]
