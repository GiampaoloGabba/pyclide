"""Unit tests for Jedi helper functions."""

import tempfile
from pathlib import Path

import pytest

from pyclide_server.jedi_helpers import jedi_to_locations


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
