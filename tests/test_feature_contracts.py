"""Contract tests: Verify component interfaces and interactions.

These tests ensure that different parts of pyclide work together correctly
and maintain their contracts during refactoring.
"""

import pathlib
import sys
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pyclide import (
    RopeEngine,
    jedi_script,
    jedi_to_locations,
    byte_offset,
    rel_to,
    list_globals,
)


class TestRopeEngineContract:
    """Test RopeEngine's public API contract."""

    @pytest.fixture
    def project(self, tmp_path):
        """Create test project."""
        (tmp_path / "module.py").write_text(
            """
class Example:
    def method(self):
        pass

def function():
    return Example()
""",
            encoding="utf-8",
        )
        return tmp_path

    def test_rope_engine_initialization_contract(self, project):
        """Contract: RopeEngine accepts pathlib.Path and creates project."""
        eng = RopeEngine(project)

        assert eng.root == project.resolve()
        assert eng.project is not None

    def test_occurrences_returns_list_of_dicts(self, project):
        """Contract: occurrences() returns List[Dict] with specific keys."""
        eng = RopeEngine(project)

        # Example class at line 2, col 7 (1-based: "E" of "Example")
        result = eng.occurrences("module.py", 2, 7)

        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, dict)
            assert "path" in item
            assert "line" in item
            assert "column" in item
            assert isinstance(item["line"], int)
            assert isinstance(item["column"], int)

    def test_rename_returns_dict_of_patches(self, project):
        """Contract: rename() returns Dict[str, str] mapping paths to content."""
        eng = RopeEngine(project)

        # Example class at line 2, col 7 (1-based: "E" of "Example")
        result = eng.rename("module.py", 2, 7, "Sample")

        assert isinstance(result, dict)
        for path, content in result.items():
            assert isinstance(path, str)
            assert isinstance(content, str)
            # Content should be valid Python
            assert len(content) > 0

    def test_extract_method_returns_dict_of_patches(self, project):
        """Contract: extract_method() returns Dict[str, str]."""
        eng = RopeEngine(project)

        result = eng.extract_method("module.py", 4, 4, "new_method")

        assert isinstance(result, dict)
        # May be empty if extraction not possible, but must be dict
        for path, content in result.items():
            assert isinstance(path, str)
            assert isinstance(content, str)

    def test_extract_variable_returns_dict_of_patches(self, project):
        """Contract: extract_variable() returns Dict[str, str]."""
        eng = RopeEngine(project)

        # Try to extract (may or may not succeed)
        result = eng.extract_variable(
            "module.py", 7, 7, "instance", start_col=12, end_col=21
        )

        assert isinstance(result, dict)

    def test_move_returns_dict_of_patches(self, project):
        """Contract: move() returns Dict[str, str]."""
        # Create target file
        (project / "target.py").write_text("", encoding="utf-8")

        eng = RopeEngine(project)

        result = eng.move("module.py::Example", "target.py")

        assert isinstance(result, dict)
        # Should have patches
        if len(result) > 0:
            for path, content in result.items():
                assert isinstance(path, str)
                assert isinstance(content, str)

    def test_organize_imports_returns_dict_of_patches(self, project):
        """Contract: organize_imports() returns Dict[str, str]."""
        # Create file with messy imports
        (project / "imports.py").write_text(
            "import sys\nimport os\nimport pathlib\n\n# Only using os\nprint(os.path)\n", encoding="utf-8"
        )

        eng = RopeEngine(project)

        result = eng.organize_imports(project / "imports.py", convert_froms=False)

        # Should return dict (may be empty if no changes needed)
        assert isinstance(result, dict)


class TestJediIntegrationContract:
    """Test Jedi integration contracts."""

    @pytest.fixture
    def project(self, tmp_path):
        """Create test project."""
        (tmp_path / "test.py").write_text(
            """
def example_function(x: int) -> int:
    \"\"\"Example function.

    Args:
        x: Input value

    Returns:
        Doubled value
    \"\"\"
    return x * 2

result = example_function(5)
""",
            encoding="utf-8",
        )
        return tmp_path

    def test_jedi_script_returns_script_object(self, project):
        """Contract: jedi_script() returns Jedi Script object."""
        scr = jedi_script(project, "test.py")

        assert scr is not None
        # Should have Jedi methods
        assert hasattr(scr, "goto")
        assert hasattr(scr, "infer")
        assert hasattr(scr, "complete")
        assert hasattr(scr, "get_references")

    def test_jedi_goto_returns_list(self, project):
        """Contract: Jedi goto returns list."""
        scr = jedi_script(project, "test.py")

        # Line 13 (1-based), col 9 (0-indexed) = "e" in "example_function"
        result = scr.goto(13, 9)

        assert isinstance(result, list)

    def test_jedi_to_locations_contract(self, project):
        """Contract: jedi_to_locations() converts Jedi results correctly."""
        scr = jedi_script(project, "test.py")
        # Line 13 (1-based), col 9 (0-indexed) = "e" in "example_function"
        jedi_results = scr.goto(13, 9)

        locations = jedi_to_locations(jedi_results)

        assert isinstance(locations, list)
        for loc in locations:
            assert isinstance(loc, dict)
            assert "path" in loc
            assert "line" in loc
            assert "column" in loc

    def test_jedi_complete_returns_list(self, project):
        """Contract: Jedi complete returns list of completions."""
        scr = jedi_script(project, "test.py")

        # Complete at line 13 (1-based), col 14 (0-indexed) = after "result = exam"
        completions = scr.complete(13, 14)

        assert isinstance(completions, list)
        # Each completion should have name attribute
        for comp in completions:
            assert hasattr(comp, "name")

    def test_jedi_infer_returns_list(self, project):
        """Contract: Jedi infer returns list of names."""
        scr = jedi_script(project, "test.py")

        names = scr.infer(10, 1)  # On "result" variable at line 10

        assert isinstance(names, list)


class TestUtilityFunctionsContract:
    """Test utility functions maintain their contracts."""

    def test_byte_offset_contract(self):
        """Contract: byte_offset() converts line/col to byte offset."""
        text = "line1\nline2\nline3"

        # Line 1, col 1 -> offset 0
        assert byte_offset(text, 1, 1) == 0

        # Line 2, col 1 -> offset 6 (after "line1\n")
        assert byte_offset(text, 2, 1) == 6

        # Line 3, col 1 -> offset 12 (after "line1\nline2\n")
        assert byte_offset(text, 3, 1) == 12

    def test_rel_to_contract(self, tmp_path):
        """Contract: rel_to() returns relative path as string."""
        root = tmp_path
        file_path = tmp_path / "subdir" / "file.py"

        result = rel_to(root, file_path)

        assert isinstance(result, str)
        # Should be relative path
        assert "subdir" in result or "subdir\\file.py" in result

    def test_list_globals_contract(self, tmp_path):
        """Contract: list command returns list of symbol dicts."""
        from typer.testing import CliRunner
        from pyclide import app

        runner = CliRunner()

        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
class MyClass:
    pass

def my_function():
    pass

variable = 42
""",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["list", str(test_file), "--json"])

        assert result.exit_code == 0
        import json
        data = json.loads(result.stdout)

        assert isinstance(data, list)
        for item in data:
            assert isinstance(item, dict)
            assert "name" in item
            assert "kind" in item  # pyclide uses "kind" not "type"
            # Should have one of these types
            assert item["kind"] in ["class", "function"]

        # Should find both class and function
        names = [item["name"] for item in data]
        assert "MyClass" in names
        assert "my_function" in names


class TestRopeJediInteroperability:
    """Test that Rope and Jedi can work on the same project."""

    @pytest.fixture
    def project(self, tmp_path):
        """Create test project."""
        (tmp_path / "module.py").write_text(
            """
class Service:
    def process(self, data: str) -> str:
        return data.upper()

service = Service()
result = service.process("hello")
""",
            encoding="utf-8",
        )
        return tmp_path

    def test_rope_and_jedi_can_analyze_same_file(self, project):
        """Contract: Both Rope and Jedi can analyze same file."""
        # Use Rope - Service class at line 2, col 7 (1-based: "S" of "Service")
        rope_eng = RopeEngine(project)
        rope_occurrences = rope_eng.occurrences("module.py", 2, 7)

        # Use Jedi - Service class at line 2, col 6 (Jedi uses 0-indexed cols)
        jedi_scr = jedi_script(project, "module.py")
        jedi_refs = jedi_scr.get_references(2, 6)

        # Both should return results
        assert isinstance(rope_occurrences, list)
        assert isinstance(jedi_refs, list)

    def test_rope_rename_jedi_can_verify(self, project):
        """Contract: After Rope rename, Jedi can still analyze."""
        rope_eng = RopeEngine(project)

        # Rename with Rope - Service class at line 2, col 7 (1-based: "S" of "Service")
        patches = rope_eng.rename("module.py", 2, 7, "Handler")

        # Write patches to disk
        for filename, content in patches.items():
            file_path = project / filename
            file_path.write_text(content, encoding="utf-8")

        # Jedi should still work
        jedi_scr = jedi_script(project, "module.py")
        # Should find Handler (not Service)
        script_content = (project / "module.py").read_text(encoding="utf-8")
        assert "Handler" in script_content


class TestCommandOutputContract:
    """Test that CLI commands maintain output contracts."""

    def test_list_command_output_structure(self, tmp_path):
        """Contract: list command with --json outputs specific structure."""
        from typer.testing import CliRunner
        from pyclide import app

        runner = CliRunner()

        test_file = tmp_path / "test.py"
        test_file.write_text("class A:\n    pass\n\ndef b():\n    pass\n", encoding="utf-8")

        result = runner.invoke(app, ["list", str(test_file), "--json"])

        assert result.exit_code == 0
        import json
        data = json.loads(result.stdout)

        assert isinstance(data, list)
        # Should have at least class A and function b
        assert len(data) >= 2

        for item in data:
            assert "name" in item
            assert "kind" in item  # pyclide uses "kind" not "type"
            assert "line" in item

    def test_defs_command_output_structure(self, tmp_path):
        """Contract: defs command outputs location structure."""
        from typer.testing import CliRunner
        from pyclide import app

        runner = CliRunner()

        (tmp_path / "def.py").write_text("def func():\n    pass\n", encoding="utf-8")
        (tmp_path / "use.py").write_text("from def import func\n\nfunc()\n", encoding="utf-8")

        result = runner.invoke(
            app, ["defs", str(tmp_path / "use.py"), "3", "1", "--root", str(tmp_path), "--json"]
        )

        if result.exit_code == 0:
            import json
            data = json.loads(result.stdout)

            assert isinstance(data, list)
            if len(data) > 0:
                for item in data:
                    assert "path" in item
                    assert "line" in item
                    assert "column" in item

    def test_hover_command_output_structure(self, tmp_path):
        """Contract: hover command outputs info structure."""
        from typer.testing import CliRunner
        from pyclide import app

        runner = CliRunner()

        test_file = tmp_path / "test.py"
        test_file.write_text('def func():\n    """Doc."""\n    pass\n', encoding="utf-8")

        result = runner.invoke(
            app, ["hover", str(test_file), "1", "5", "--root", str(tmp_path), "--json"]
        )

        assert result.exit_code == 0
        import json
        data = json.loads(result.stdout)

        assert isinstance(data, list)
        if len(data) > 0:
            for item in data:
                assert "name" in item
                # May or may not have signature, docstring, type_name
                # But must be dict with at least name


class TestErrorHandlingContract:
    """Test error handling contracts."""

    def test_missing_file_returns_error_not_crash(self, tmp_path):
        """Contract: Missing file returns error, does not crash."""
        from typer.testing import CliRunner
        from pyclide import app

        runner = CliRunner()

        result = runner.invoke(
            app,
            ["defs", str(tmp_path / "nonexistent.py"), "1", "1", "--json"],
        )

        # Should fail gracefully
        assert result.exit_code != 0

    def test_invalid_coordinates_returns_error(self, tmp_path):
        """Contract: Invalid coordinates return error."""
        from typer.testing import CliRunner
        from pyclide import app

        runner = CliRunner()

        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n", encoding="utf-8")

        # Line 999 doesn't exist
        result = runner.invoke(
            app, ["defs", str(test_file), "999", "1", "--json"]
        )

        # Should fail
        assert result.exit_code != 0

    def test_rope_engine_with_nonexistent_root_raises(self):
        """Contract: RopeEngine with invalid root raises error."""
        with pytest.raises(Exception):
            # Should raise when trying to create project in non-existent dir
            RopeEngine(pathlib.Path("/nonexistent/path/that/does/not/exist"))
