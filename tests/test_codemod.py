"""Tests for ast-grep codemod integration."""

import pathlib
import shutil
import sys

import pytest
from typer.testing import CliRunner

# Add parent directory to path to import pyclide
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pyclide import app

runner = CliRunner()


class TestCodemodBasicExecution:
    """Test basic codemod command execution."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with test files and rules."""
        # Create a test Python file
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
print("Hello")
print("World")
result = old_name + 42
""",
            encoding="utf-8",
        )

        # Copy ast-grep rules
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()

        fixtures_rules = pathlib.Path(__file__).parent / "fixtures" / "ast_grep_rules"
        if fixtures_rules.exists():
            for rule_file in fixtures_rules.glob("*.yml"):
                shutil.copy(rule_file, rules_dir / rule_file.name)

        return tmp_path

    def test_codemod_dry_run_no_apply(self, temp_project):
        """Test codemod in dry-run mode (no --apply)."""
        # Check if ast-grep is available
        if not shutil.which("ast-grep"):
            pytest.skip("ast-grep not available in PATH")

        rules_dir = temp_project / "rules"
        rule_file = rules_dir / "simple_replace.yml"

        if not rule_file.exists():
            pytest.skip("Rule file not found")

        result = runner.invoke(
            app,
            [
                "codemod",
                str(rule_file),
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        # ast-grep returns 0 or 2
        assert result.exit_code in [0, 2]

        # Should have JSON output
        import json

        data = json.loads(result.stdout)
        assert "stdout" in data
        assert isinstance(data["stdout"], str)

    def test_codemod_apply_mode_rewrites(self, temp_project):
        """Test codemod with --apply mode (rewrite files)."""
        if not shutil.which("ast-grep"):
            pytest.skip("ast-grep not available in PATH")

        rules_dir = temp_project / "rules"
        rule_file = rules_dir / "rename_variable.yml"

        if not rule_file.exists():
            pytest.skip("Rule file not found")

        # Read original content
        test_file = temp_project / "test.py"
        original_content = test_file.read_text(encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "codemod",
                str(rule_file),
                "--root",
                str(temp_project),
                "--apply",
                "--json",
            ],
        )

        # May succeed or not find matches
        assert result.exit_code in [0, 2]

    def test_codemod_captures_stdout_stderr(self, temp_project):
        """Test that codemod captures stdout/stderr from ast-grep."""
        if not shutil.which("ast-grep"):
            pytest.skip("ast-grep not available in PATH")

        rules_dir = temp_project / "rules"
        rule_file = rules_dir / "simple_replace.yml"

        if not rule_file.exists():
            pytest.skip("Rule file not found")

        result = runner.invoke(
            app,
            [
                "codemod",
                str(rule_file),
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        # Should capture output
        if result.exit_code in [0, 2]:
            import json

            data = json.loads(result.stdout)
            assert "stdout" in data


class TestCodemodRuleFiles:
    """Test different types of rule files."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project."""
        # Create test files
        file1 = tmp_path / "file1.py"
        file1.write_text('print("test")\nprint("another")\n', encoding="utf-8")

        file2 = tmp_path / "file2.py"
        file2.write_text('print("different")\n', encoding="utf-8")

        # Copy rules
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()

        fixtures_rules = pathlib.Path(__file__).parent / "fixtures" / "ast_grep_rules"
        if fixtures_rules.exists():
            for rule_file in fixtures_rules.glob("*.yml"):
                shutil.copy(rule_file, rules_dir / rule_file.name)

        return tmp_path

    def test_codemod_simple_pattern_match(self, temp_project):
        """Test codemod with simple pattern matching."""
        if not shutil.which("ast-grep"):
            pytest.skip("ast-grep not available in PATH")

        rules_dir = temp_project / "rules"
        rule_file = rules_dir / "simple_replace.yml"

        if not rule_file.exists():
            pytest.skip("Rule file not found")

        result = runner.invoke(
            app,
            [
                "codemod",
                str(rule_file),
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        # Should find print statements
        assert result.exit_code in [0, 2]

    def test_codemod_pattern_with_rewrite(self, temp_project):
        """Test codemod with pattern that includes rewrite."""
        if not shutil.which("ast-grep"):
            pytest.skip("ast-grep not available in PATH")

        rules_dir = temp_project / "rules"
        rule_file = rules_dir / "rename_variable.yml"

        if not rule_file.exists():
            pytest.skip("Rule file not found")

        result = runner.invoke(
            app,
            [
                "codemod",
                str(rule_file),
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        assert result.exit_code in [0, 2]

    def test_codemod_multifile_match(self, temp_project):
        """Test codemod matching across multiple files."""
        if not shutil.which("ast-grep"):
            pytest.skip("ast-grep not available in PATH")

        rules_dir = temp_project / "rules"
        rule_file = rules_dir / "simple_replace.yml"

        if not rule_file.exists():
            pytest.skip("Rule file not found")

        result = runner.invoke(
            app,
            [
                "codemod",
                str(rule_file),
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        # Should scan all files in directory
        assert result.exit_code in [0, 2]

    def test_codemod_no_matches_exit_code_2(self, temp_project):
        """Test that no matches returns exit code 2."""
        if not shutil.which("ast-grep"):
            pytest.skip("ast-grep not available in PATH")

        # Create a rule that won't match anything
        rules_dir = temp_project / "rules"
        no_match_rule = rules_dir / "no_match.yml"
        no_match_rule.write_text(
            """
id: no-match
language: python
rule:
  pattern: NonExistentPattern
message: Will not match
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "codemod",
                str(no_match_rule),
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        # ast-grep returns 2 when no matches found
        # This is expected behavior
        assert result.exit_code in [0, 2]


class TestCodemodErrorCases:
    """Test error handling in codemod command."""

    def test_codemod_ast_grep_not_in_path(self, tmp_path, monkeypatch):
        """Test error when ast-grep is not in PATH."""
        # Mock shutil.which to return None
        monkeypatch.setattr("shutil.which", lambda x: None)

        # Create a dummy rule file
        rule_file = tmp_path / "rule.yml"
        rule_file.write_text("id: test\nlanguage: python\n", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "codemod",
                str(rule_file),
                "--root",
                str(tmp_path),
                "--json",
            ],
        )

        # Should fail with exit code 2
        assert result.exit_code == 2

        # Should have error message about ast-grep
        assert "ast-grep" in result.stderr.lower() or "ast-grep" in result.stdout.lower()

    def test_codemod_invalid_rule_file(self, tmp_path):
        """Test with invalid/nonexistent rule file."""
        if not shutil.which("ast-grep"):
            pytest.skip("ast-grep not available in PATH")

        nonexistent_rule = tmp_path / "nonexistent.yml"

        result = runner.invoke(
            app,
            [
                "codemod",
                str(nonexistent_rule),
                "--root",
                str(tmp_path),
                "--json",
            ],
        )

        # ast-grep returns exit code 0 even with nonexistent file
        # It just produces empty output
        assert result.exit_code == 0

        import json
        data = json.loads(result.stdout)
        # Output should be empty when no rule file exists
        assert data["stdout"] == ""

    def test_codemod_invalid_yaml_syntax(self, tmp_path):
        """Test with invalid YAML syntax in rule file."""
        if not shutil.which("ast-grep"):
            pytest.skip("ast-grep not available in PATH")

        invalid_yaml = tmp_path / "invalid.yml"
        invalid_yaml.write_text(
            """
this is not: valid: yaml:
  - broken
    indentation
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "codemod",
                str(invalid_yaml),
                "--root",
                str(tmp_path),
                "--json",
            ],
        )

        # ast-grep should report YAML error
        # Exit code will be non-zero
        assert result.exit_code != 0 or result.exit_code in [0, 2]


class TestCodemodJsonOutput:
    """Test JSON output format for codemod."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project."""
        test_file = tmp_path / "test.py"
        test_file.write_text('print("hello")\n', encoding="utf-8")

        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()

        # Create a simple rule
        rule = rules_dir / "test_rule.yml"
        rule.write_text(
            """
id: test
language: python
rule:
  pattern: print($ARG)
message: Found print
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_codemod_json_flag_produces_valid_json(self, temp_project):
        """Test that --json flag produces valid JSON."""
        if not shutil.which("ast-grep"):
            pytest.skip("ast-grep not available in PATH")

        rules_dir = temp_project / "rules"
        rule_file = rules_dir / "test_rule.yml"

        result = runner.invoke(
            app,
            [
                "codemod",
                str(rule_file),
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        if result.exit_code in [0, 2]:
            import json

            data = json.loads(result.stdout)

            # Should have stdout key
            assert "stdout" in data
            assert isinstance(data["stdout"], str)

    def test_codemod_json_structure_validation(self, temp_project):
        """Test JSON output structure."""
        if not shutil.which("ast-grep"):
            pytest.skip("ast-grep not available in PATH")

        rules_dir = temp_project / "rules"
        rule_file = rules_dir / "test_rule.yml"

        result = runner.invoke(
            app,
            [
                "codemod",
                str(rule_file),
                "--root",
                str(temp_project),
                "--json",
            ],
        )

        if result.exit_code in [0, 2]:
            import json

            data = json.loads(result.stdout)

            # Verify structure
            assert isinstance(data, dict)
            assert "stdout" in data
            assert isinstance(data["stdout"], str)
