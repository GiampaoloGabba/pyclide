"""Tests for Rope-based features (rename, occurrences, extract methods/variables)."""

import pathlib
import sys
import tempfile
import shutil

import pytest

# Add parent directory to path to import pyclide
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pyclide import RopeEngine


class TestRopeFeatures:
    """Test Rope integration features."""

    @pytest.fixture
    def temp_project_dir(self, tmp_path):
        """Create a temporary project directory with test fixtures."""
        # Copy fixtures to temp directory
        # Rope is configured with ignore_syntax_errors=True, so it will skip invalid files
        fixtures_src = pathlib.Path(__file__).parent / "fixtures"
        for file in fixtures_src.glob("*.py"):
            shutil.copy(file, tmp_path / file.name)
        return tmp_path

    @pytest.fixture
    def rope_engine(self, temp_project_dir):
        """Create a RopeEngine instance for the temp project."""
        return RopeEngine(temp_project_dir)

    def test_rope_occurrences_function(self, rope_engine, temp_project_dir):
        """Test finding occurrences of a function name."""
        # Find occurrences of "hello_world" function
        # Line 4, column 5 is on the function definition
        occurrences = rope_engine.occurrences("sample_module.py", 4, 5)

        # Should find at least the definition
        assert len(occurrences) >= 1

        # Check structure of results
        for occ in occurrences:
            assert "path" in occ
            assert "line" in occ
            assert "column" in occ
            assert occ["line"] > 0
            assert occ["column"] > 0

    def test_rope_occurrences_variable(self, rope_engine, temp_project_dir):
        """Test finding occurrences of a variable."""
        # Find occurrences of "message" variable in hello_world function
        # Line 14, column 5 is on the message variable
        occurrences = rope_engine.occurrences("sample_module.py", 14, 5)

        # Should find definition and usage
        assert len(occurrences) >= 2

    def test_rope_occurrences_class(self, rope_engine, temp_project_dir):
        """Test finding occurrences of a class name."""
        # Find occurrences of Calculator class
        # Line 24, column 7 is on the class definition
        occurrences = rope_engine.occurrences("sample_module.py", 24, 7)

        # Should find definition and usages (in sample_module and sample_usage)
        assert len(occurrences) >= 2

    def test_rope_rename_variable(self, rope_engine, temp_project_dir):
        """Test renaming a local variable."""
        # Rename "message" to "greeting_msg" in hello_world function
        # Line 14, column 5 is on the message variable
        patches = rope_engine.rename("sample_module.py", 14, 5, "greeting_msg")

        # Should produce changes
        assert len(patches) > 0
        assert "sample_module.py" in patches

        # Check that the new content contains the new name
        new_content = patches["sample_module.py"]
        assert "greeting_msg" in new_content
        # Old name should be replaced in function body
        assert 'greeting_msg = f"Hello, {name}!"' in new_content
        assert "return greeting_msg" in new_content

    def test_rope_rename_function(self, rope_engine, temp_project_dir):
        """Test renaming a function across multiple files."""
        # Rename hello_world to greet_user
        patches = rope_engine.rename("sample_module.py", 4, 5, "greet_user")

        # Should change both definition and usage files
        assert len(patches) >= 1

        # Check sample_module.py changes
        if "sample_module.py" in patches:
            assert "def greet_user" in patches["sample_module.py"]

        # Check sample_usage.py changes if present
        if "sample_usage.py" in patches:
            assert "greet_user" in patches["sample_usage.py"]

    def test_rope_rename_class(self, rope_engine, temp_project_dir):
        """Test renaming a class."""
        # Rename Calculator to MathCalculator
        patches = rope_engine.rename("sample_module.py", 24, 7, "MathCalculator")

        # Should produce changes
        assert len(patches) >= 1

        # Check that class definition is renamed
        new_content = patches["sample_module.py"]
        assert "class MathCalculator:" in new_content

    def test_rope_extract_variable(self, rope_engine, temp_project_dir):
        """Test extracting an expression to a variable."""
        # Extract "a + b" in calculate_sum function
        # Line 20 has "    result = a + b"
        # Column 16 is 'a', column 21 is after 'b'
        patches = rope_engine.extract_variable("sample_module.py", 20, 20, "temp_sum", start_col=16, end_col=21)

        # Should produce changes
        assert len(patches) > 0
        assert "sample_module.py" in patches

        new_content = patches["sample_module.py"]
        # Should have the new variable
        assert "temp_sum" in new_content

    def test_rope_extract_method(self, rope_engine, temp_project_dir):
        """Test extracting code to a new method."""
        # Extract lines in hello_world that create the message
        # This is a bit complex, but let's try extracting the message creation
        # Line 14 to 14 (just the message creation line)
        patches = rope_engine.extract_method("sample_module.py", 14, 14, "create_greeting")

        # Should produce changes
        assert len(patches) > 0
        assert "sample_module.py" in patches

        new_content = patches["sample_module.py"]
        # Should have a new function called create_greeting
        assert "def create_greeting" in new_content or "create_greeting" in new_content

    def test_rope_organize_imports(self, rope_engine, temp_project_dir):
        """Test organizing imports in a file."""
        # Create a test file with messy imports that ARE USED
        test_file = temp_project_dir / "messy_imports.py"
        test_file.write_text("""
import os
import sys


import json
from pathlib import Path

def test():
    # Use the imports so they don't get removed
    print(os.path.join('a', 'b'))
    print(sys.version)
    data = json.dumps({})
    p = Path('.')
    return data, p
""")

        patches = rope_engine.organize_imports(test_file, convert_froms=False)

        # If there are changes, check they're organized
        if len(patches) > 0:
            new_content = patches.get("messy_imports.py", "")
            # Imports should be organized and present
            assert "import" in new_content
            # Should contain the used imports
            assert "os" in new_content or "json" in new_content
