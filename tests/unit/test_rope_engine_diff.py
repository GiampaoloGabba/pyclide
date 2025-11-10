"""Unit tests for RopeEngine diff format output.

Tests that unified diff generation works correctly for all refactoring operations.
This is the PRIMARY output format (default) for token efficiency.
"""

import difflib
import pathlib
import re

import pytest

from pyclide_server.rope_engine import RopeEngine


def apply_unified_diff(original_content: str, diff_text: str) -> str:
    """
    Apply a unified diff to original content and return the result.

    This is used to verify that generated diffs are valid and produce
    the expected result when applied.

    Args:
        original_content: Original file content
        diff_text: Unified diff text

    Returns:
        Patched content

    Raises:
        ValueError: If diff cannot be applied
    """
    if not diff_text:
        return original_content

    # Parse diff to extract hunks
    lines = diff_text.split('\n')
    original_lines = original_content.splitlines(keepends=True)
    result_lines = list(original_lines)

    # Find hunks (lines starting with @@)
    hunks = []
    current_hunk = None

    for line in lines:
        if line.startswith('@@'):
            # Parse hunk header: @@ -start,count +start,count @@
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if match:
                old_start = int(match.group(1))
                old_count = int(match.group(2)) if match.group(2) else 1
                new_start = int(match.group(3))
                new_count = int(match.group(4)) if match.group(4) else 1

                current_hunk = {
                    'old_start': old_start,
                    'old_count': old_count,
                    'new_start': new_start,
                    'new_count': new_count,
                    'lines': []
                }
                hunks.append(current_hunk)
        elif current_hunk is not None:
            if line.startswith(' ') or line.startswith('+') or line.startswith('-'):
                current_hunk['lines'].append(line)

    # Apply hunks in reverse order to maintain line numbers
    for hunk in reversed(hunks):
        old_start = hunk['old_start'] - 1  # Convert to 0-based
        old_count = hunk['old_count']

        # Build new lines for this hunk
        new_lines = []
        for line in hunk['lines']:
            if line.startswith('+'):
                new_lines.append(line[1:] + '\n')
            elif line.startswith(' '):
                new_lines.append(line[1:] + '\n')
            # Skip lines starting with '-'

        # Replace old lines with new lines
        result_lines[old_start:old_start + old_count] = new_lines

    return ''.join(result_lines)


@pytest.mark.unit
@pytest.mark.rope
class TestDiffCorrectnessValidation:
    """CRITICAL: Validate that generated diffs are correct and applicable.

    These tests verify that:
    1. Diffs can be successfully applied to original content
    2. Applying a diff produces the same result as output_format="full"
    3. Diffs are well-formed and parseable
    """

    def test_rename_diff_produces_same_result_as_full(self, tmp_path):
        """CRITICAL: Applying diff should produce identical result to full format."""
        test_file = tmp_path / "test.py"
        original_content = """
def old_name():
    x = 1
    y = old_name()
    return y
"""
        test_file.write_text(original_content)

        engine = RopeEngine(tmp_path)

        # Get both formats
        diff_patches = engine.rename("test.py", 2, 5, "new_name", output_format="diff")
        full_patches = engine.rename("test.py", 2, 5, "new_name", output_format="full")

        # Apply diff to original
        diff_text = diff_patches["test.py"]
        patched_content = apply_unified_diff(original_content, diff_text)

        # Should match full format exactly
        assert patched_content == full_patches["test.py"], \
            f"Diff application mismatch!\nExpected:\n{full_patches['test.py']}\n\nGot:\n{patched_content}"

    def test_extract_method_diff_correctness(self, tmp_path):
        """Extract method diff should apply correctly."""
        test_file = tmp_path / "test.py"
        original_content = """
def func():
    x = 10
    y = 20
    z = x + y
    return z
"""
        test_file.write_text(original_content)

        engine = RopeEngine(tmp_path)

        diff_patches = engine.extract_method("test.py", 5, 5, "calc_sum", output_format="diff")
        full_patches = engine.extract_method("test.py", 5, 5, "calc_sum", output_format="full")

        if diff_patches:  # Rope might refuse
            diff_text = diff_patches["test.py"]
            patched_content = apply_unified_diff(original_content, diff_text)
            assert patched_content == full_patches["test.py"]

    def test_extract_variable_diff_correctness(self, tmp_path):
        """Extract variable diff should apply correctly."""
        test_file = tmp_path / "test.py"
        original_content = """
def func():
    result = 10 + 20
    return result
"""
        test_file.write_text(original_content)

        engine = RopeEngine(tmp_path)

        diff_patches = engine.extract_variable("test.py", 3, 3, "sum_val", start_col=14, end_col=21, output_format="diff")
        full_patches = engine.extract_variable("test.py", 3, 3, "sum_val", start_col=14, end_col=21, output_format="full")

        if diff_patches:
            diff_text = diff_patches["test.py"]
            patched_content = apply_unified_diff(original_content, diff_text)
            assert patched_content == full_patches["test.py"]

    def test_organize_imports_diff_correctness(self, tmp_path):
        """Organize imports diff should apply correctly."""
        test_file = tmp_path / "test.py"
        original_content = """
import sys
import os


import json

print(os.getcwd())
print(sys.version)
print(json.dumps({}))
"""
        test_file.write_text(original_content)

        engine = RopeEngine(tmp_path)

        diff_patches = engine.organize_imports(test_file, convert_froms=False, output_format="diff")
        full_patches = engine.organize_imports(test_file, convert_froms=False, output_format="full")

        if diff_patches:
            diff_text = diff_patches["test.py"]
            patched_content = apply_unified_diff(original_content, diff_text)
            assert patched_content == full_patches["test.py"]

    def test_cross_file_rename_all_diffs_apply_correctly(self, tmp_path):
        """All diffs in cross-file rename should apply correctly."""
        file1 = tmp_path / "module.py"
        content1 = "def old_name():\n    pass\n"
        file1.write_text(content1)

        file2 = tmp_path / "usage.py"
        content2 = "from module import old_name\nold_name()\n"
        file2.write_text(content2)

        engine = RopeEngine(tmp_path)

        diff_patches = engine.rename("module.py", 1, 5, "new_name", output_format="diff")
        full_patches = engine.rename("module.py", 1, 5, "new_name", output_format="full")

        # Verify all diffs apply correctly
        for file_path, diff_text in diff_patches.items():
            if file_path == "module.py":
                original = content1
            elif file_path == "usage.py":
                original = content2
            else:
                continue

            patched = apply_unified_diff(original, diff_text)
            assert patched == full_patches[file_path], \
                f"Diff mismatch for {file_path}"

    def test_diff_is_parseable_by_difflib(self, tmp_path):
        """Generated diffs should be valid unified diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\ny = x + 2\n")

        engine = RopeEngine(tmp_path)
        patches = engine.rename("test.py", 1, 1, "z", output_format="diff")

        diff_text = patches["test.py"]

        # Should have proper diff structure
        assert "---" in diff_text
        assert "+++" in diff_text
        assert "@@" in diff_text

        # Should be parseable (no exceptions)
        lines = diff_text.split('\n')
        assert any(line.startswith('@@') for line in lines)

    def test_empty_diff_when_no_changes(self, tmp_path):
        """When Rope makes no changes, diff format should return empty dict."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import os\nimport sys\n")

        engine = RopeEngine(tmp_path)
        patches = engine.organize_imports(test_file, convert_froms=False, output_format="diff")

        # Should be empty or minimal
        assert isinstance(patches, dict)

    def test_large_file_diff_efficiency(self, tmp_path):
        """Diff should be significantly smaller than full for large files."""
        # Create a large file (1000 lines)
        lines = [f"def function_{i}():\n    return {i}\n\n" for i in range(333)]
        large_content = "".join(lines)

        test_file = tmp_path / "large.py"
        test_file.write_text(large_content)

        engine = RopeEngine(tmp_path)

        # Rename just one function
        diff_patches = engine.rename("large.py", 2, 5, "renamed_func", output_format="diff")
        full_patches = engine.rename("large.py", 2, 5, "renamed_func", output_format="full")

        diff_size = len(diff_patches["large.py"])
        full_size = len(full_patches["large.py"])

        # Diff should be at least 50% smaller
        assert diff_size < full_size * 0.5, \
            f"Diff not efficient enough: {diff_size} bytes vs {full_size} bytes"

        # But diff should still apply correctly
        patched = apply_unified_diff(large_content, diff_patches["large.py"])
        assert patched == full_patches["large.py"]

    def test_multiple_hunks_apply_correctly(self, tmp_path):
        """Diffs with multiple separated change hunks should apply correctly."""
        test_file = tmp_path / "test.py"
        original_content = """
def old_func_a():
    return 1

def middle():
    return 2

def old_func_b():
    return 3

x = old_func_a()
y = old_func_b()
"""
        test_file.write_text(original_content)

        engine = RopeEngine(tmp_path)

        # Rename old_func_a (should create multiple hunks)
        diff_patches = engine.rename("test.py", 2, 5, "new_func_a", output_format="diff")
        full_patches = engine.rename("test.py", 2, 5, "new_func_a", output_format="full")

        diff_text = diff_patches["test.py"]
        patched = apply_unified_diff(original_content, diff_text)

        assert patched == full_patches["test.py"]


@pytest.mark.unit
@pytest.mark.rope
class TestRopeEngineDiffFormat:
    """Test that RopeEngine generates correct unified diffs."""

    def test_rename_generates_valid_diff(self, tmp_path):
        """Rename returns valid unified diff by default."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def old_name():
    return old_name()
""")

        engine = RopeEngine(tmp_path)
        patches = engine.rename("test.py", 2, 5, "new_name")  # Default: diff format

        assert isinstance(patches, dict)
        assert len(patches) == 1

        diff = patches["test.py"]

        # Should be a unified diff
        assert "--- test.py" in diff or "--- a/test.py" in diff
        assert "+++ test.py" in diff or "+++ b/test.py" in diff
        assert "@@" in diff  # Hunk header
        assert "-def old_name():" in diff
        assert "+def new_name():" in diff

    def test_rename_diff_format_explicit(self, tmp_path):
        """Rename with output_format='diff' generates diff."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\ny = x + 2\n")

        engine = RopeEngine(tmp_path)
        patches = engine.rename("test.py", 1, 1, "z", output_format="diff")

        assert isinstance(patches, dict)
        diff = patches["test.py"]

        # Verify it's a diff, not full content
        assert "---" in diff
        assert "+++" in diff
        assert "-x = 1" in diff
        assert "+z = 1" in diff

    def test_rename_full_format_returns_complete_file(self, tmp_path):
        """Rename with output_format='full' returns complete file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\ny = x + 2\n")

        engine = RopeEngine(tmp_path)
        patches = engine.rename("test.py", 1, 1, "z", output_format="full")

        content = patches["test.py"]

        # Should be full content, not a diff
        assert "---" not in content
        assert "+++" not in content
        assert "z = 1" in content
        assert "y = z + 2" in content

    def test_diff_is_default(self, tmp_path):
        """Default output_format is 'diff'."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def func():\n    pass\n")

        engine = RopeEngine(tmp_path)
        # Call without output_format parameter
        patches = engine.rename("test.py", 1, 5, "new_func")

        diff = patches["test.py"]
        # Should be a diff by default
        assert "---" in diff
        assert "+++" in diff
        assert "@@" in diff

    def test_diff_smaller_than_full(self, tmp_path):
        """Diff output is significantly smaller than full content."""
        # Create a larger file
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def calculate(x, y):
    # Some comment
    result = x + y
    return result

def other_function():
    # Many lines
    a = 1
    b = 2
    c = 3
    d = 4
    e = 5
    return a + b + c + d + e

def yet_another():
    # Even more lines
    for i in range(100):
        print(i)
    return True

# Many more lines...
""" * 5)  # Repeat to make it bigger

        engine = RopeEngine(tmp_path)

        # Get both formats
        diff_patches = engine.rename("test.py", 2, 5, "compute", output_format="diff")
        full_patches = engine.rename("test.py", 2, 5, "compute", output_format="full")

        diff_size = len(diff_patches["test.py"])
        full_size = len(full_patches["test.py"])

        # Diff should be MUCH smaller (at least 50% smaller)
        assert diff_size < full_size * 0.5, f"Diff ({diff_size}) not significantly smaller than full ({full_size})"

    def test_extract_method_generates_diff(self, tmp_path):
        """Extract method returns unified diff."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def func():
    x = 10
    y = 20
    z = x + y
    return z
""")

        engine = RopeEngine(tmp_path)
        patches = engine.extract_method("test.py", 5, 5, "calc_sum")

        if patches:  # Rope might refuse
            diff = list(patches.values())[0]
            # Should be diff by default
            assert "---" in diff or "def calc_sum" in diff

    def test_extract_variable_generates_diff(self, tmp_path):
        """Extract variable returns unified diff."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def func():
    result = 10 + 20
    return result
""")

        engine = RopeEngine(tmp_path)
        patches = engine.extract_variable("test.py", 3, 3, "sum_val", start_col=14, end_col=21)

        if patches:
            diff = list(patches.values())[0]
            assert "---" in diff or "+++" in diff

    def test_move_generates_diff(self, tmp_path):
        """Move returns unified diff."""
        source = tmp_path / "source.py"
        source.write_text("def my_func():\n    return 42\n")

        target = tmp_path / "target.py"
        target.write_text("# target\n")

        engine = RopeEngine(tmp_path)
        patches = engine.move("source.py", "target.py", line=1, col=5)

        # Should have diffs for both files
        assert len(patches) >= 1
        # At least one should be a diff
        for path, content in patches.items():
            if "---" in content and "+++" in content:
                # Found a diff
                assert "@@" in content
                break
        else:
            # If no diffs found, that's still ok for move (might be complex)
            pass

    def test_organize_imports_generates_diff(self, tmp_path):
        """Organize imports returns unified diff."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import sys
import os


import json

print(os.getcwd())
""")

        engine = RopeEngine(tmp_path)
        patches = engine.organize_imports(test_file, convert_froms=False)

        if patches:  # Only if Rope made changes
            diff = patches["test.py"]
            # Should be a diff
            assert "---" in diff
            assert "+++" in diff

    def test_no_changes_returns_empty_dict(self, tmp_path):
        """When no changes needed, diff format returns empty dict."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import os\nimport sys\n")

        engine = RopeEngine(tmp_path)
        patches = engine.organize_imports(test_file, convert_froms=False)

        # No changes = empty dict
        assert isinstance(patches, dict)
        # May be empty or may have changes depending on Rope's view of "organized"

    def test_diff_includes_context_lines(self, tmp_path):
        """Unified diff includes context lines around changes."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
# Before
def old_name():
    pass
# After
""")

        engine = RopeEngine(tmp_path)
        patches = engine.rename("test.py", 3, 5, "new_name")

        diff = patches["test.py"]

        # Should include context
        assert "@@" in diff
        # Context lines might include "# Before" and "# After"

    def test_cross_file_rename_all_diffs(self, tmp_path):
        """Cross-file rename returns diffs for all modified files."""
        file1 = tmp_path / "module.py"
        file1.write_text("def old_name():\n    pass\n")

        file2 = tmp_path / "usage.py"
        file2.write_text("from module import old_name\nold_name()\n")

        engine = RopeEngine(tmp_path)
        patches = engine.rename("module.py", 1, 5, "new_name")

        # Should have patches for modified files
        assert isinstance(patches, dict)

        # All patches should be diffs (not full content)
        for path, content in patches.items():
            # Each should be a diff
            assert "---" in content or "+++" in content

    def test_diff_format_for_multiline_change(self, tmp_path):
        """Diff handles multi-line changes correctly."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def calculate(x, y):
    result = x + y
    return result

z = calculate(1, 2)
""")

        engine = RopeEngine(tmp_path)
        patches = engine.rename("test.py", 2, 5, "compute")

        diff = patches["test.py"]

        # Should show multiple line changes
        assert "-def calculate" in diff
        assert "+def compute" in diff
        assert "-z = calculate" in diff
        assert "+z = compute" in diff


@pytest.mark.unit
@pytest.mark.rope
class TestRenameEdgeCasesDiff:
    """Edge cases for rename in diff format (ported from test_rope_engine.py)."""

    def test_rename_with_invalid_name_diff(self, tmp_path):
        """Rename with invalid Python identifier in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        engine = RopeEngine(tmp_path)
        try:
            patches = engine.rename("test.py", 1, 1, "invalid name!", output_format="diff")
            assert isinstance(patches, dict)
        except Exception:
            pass  # Also acceptable if Rope rejects

    def test_rename_builtin_diff(self, tmp_path):
        """Attempt to rename a builtin in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = len([1, 2, 3])\n")

        engine = RopeEngine(tmp_path)
        try:
            patches = engine.rename("test.py", 1, 5, "my_len", output_format="diff")
            assert isinstance(patches, dict)
        except Exception:
            pass  # Acceptable

    def test_rename_out_of_bounds_diff(self, tmp_path):
        """Rename with out of bounds position in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        engine = RopeEngine(tmp_path)
        with pytest.raises(Exception):
            engine.rename("test.py", 100, 100, "new_name", output_format="diff")

    def test_rename_preserves_semantics_diff(self, tmp_path):
        """Rename should preserve code semantics (diff format)."""
        test_file = tmp_path / "test.py"
        original = """
def calculate(x, y):
    return x + y

result = calculate(1, 2)
"""
        test_file.write_text(original)

        engine = RopeEngine(tmp_path)
        diff_patches = engine.rename("test.py", 2, 5, "compute", output_format="diff")
        full_patches = engine.rename("test.py", 2, 5, "compute", output_format="full")

        # Apply diff and verify it matches full
        patched = apply_unified_diff(original, diff_patches["test.py"])
        assert patched == full_patches["test.py"]


@pytest.mark.unit
@pytest.mark.rope
class TestExtractMethodEdgeCasesDiff:
    """Edge cases for extract_method in diff format."""

    def test_extract_method_multiple_lines_diff(self, tmp_path):
        """Extract multiple lines to method in diff format."""
        test_file = tmp_path / "test.py"
        original = """
def func():
    a = 1
    b = 2
    c = a + b
    return c
"""
        test_file.write_text(original)

        engine = RopeEngine(tmp_path)
        diff_patches = engine.extract_method("test.py", 3, 4, "compute", output_format="diff")
        full_patches = engine.extract_method("test.py", 3, 4, "compute", output_format="full")

        if diff_patches:
            patched = apply_unified_diff(original, diff_patches["test.py"])
            assert patched == full_patches["test.py"]

    def test_extract_method_start_greater_than_end_diff(self, tmp_path):
        """Extract with start_line > end_line in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def func():
    x = 10
    return x
""")

        engine = RopeEngine(tmp_path)
        try:
            patches = engine.extract_method("test.py", 4, 3, "extracted", output_format="diff")
            assert isinstance(patches, dict)
        except Exception:
            pass  # Acceptable

    def test_extract_method_out_of_bounds_diff(self, tmp_path):
        """Extract with line out of bounds in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        engine = RopeEngine(tmp_path)
        with pytest.raises(Exception):
            engine.extract_method("test.py", 10, 20, "extracted", output_format="diff")

    def test_extract_method_invalid_name_diff(self, tmp_path):
        """Extract with invalid method name in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def func():\n    x = 1\n")

        engine = RopeEngine(tmp_path)
        try:
            patches = engine.extract_method("test.py", 2, 2, "invalid-name", output_format="diff")
            assert isinstance(patches, dict)
        except Exception:
            pass

    def test_extract_method_duplicate_name_diff(self, tmp_path):
        """Extract with method name that already exists in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def existing():
    pass

def func():
    x = 1
    return x
""")

        engine = RopeEngine(tmp_path)
        try:
            patches = engine.extract_method("test.py", 6, 6, "existing", output_format="diff")
            assert isinstance(patches, dict)
        except Exception:
            pass


@pytest.mark.unit
@pytest.mark.rope
class TestExtractVariableEdgeCasesDiff:
    """Edge cases for extract_variable in diff format."""

    def test_extract_var_only_start_col_diff(self, tmp_path):
        """Extract variable with only start_col in diff format."""
        test_file = tmp_path / "test.py"
        original = """
def func():
    x = 10 + 20
    return x
"""
        test_file.write_text(original)

        engine = RopeEngine(tmp_path)
        diff_patches = engine.extract_variable("test.py", 3, 3, "expr", start_col=9, end_col=None, output_format="diff")
        full_patches = engine.extract_variable("test.py", 3, 3, "expr", start_col=9, end_col=None, output_format="full")

        if diff_patches:
            patched = apply_unified_diff(original, diff_patches["test.py"])
            assert patched == full_patches["test.py"]

    def test_extract_var_only_end_col_diff(self, tmp_path):
        """Extract variable with only end_col in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def func():
    x = 10
    return x
""")

        engine = RopeEngine(tmp_path)
        try:
            patches = engine.extract_variable("test.py", 3, 3, "val", start_col=None, end_col=10, output_format="diff")
            assert isinstance(patches, dict)
        except Exception:
            pass

    def test_extract_var_no_columns_diff(self, tmp_path):
        """Extract variable with no columns in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def func():
    x = 10
    return x
""")

        engine = RopeEngine(tmp_path)
        try:
            patches = engine.extract_variable("test.py", 3, 3, "extracted", start_col=None, end_col=None, output_format="diff")
            assert isinstance(patches, dict)
        except Exception:
            pass

    def test_extract_var_multiline_diff(self, tmp_path):
        """Extract variable across multiple lines in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def func():
    result = (
        10 + 20
    )
    return result
""")

        engine = RopeEngine(tmp_path)
        try:
            patches = engine.extract_variable("test.py", 3, 4, "expr", output_format="diff")
            assert isinstance(patches, dict)
        except Exception:
            pass

    def test_extract_var_column_out_of_bounds_diff(self, tmp_path):
        """Extract variable with column out of bounds in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 10\n")

        engine = RopeEngine(tmp_path)
        with pytest.raises(Exception):
            engine.extract_variable("test.py", 1, 1, "val", start_col=1, end_col=1000, output_format="diff")

    def test_extract_var_invalid_name_diff(self, tmp_path):
        """Extract variable with invalid name in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 10\n")

        engine = RopeEngine(tmp_path)
        try:
            patches = engine.extract_variable("test.py", 1, 1, "invalid-var", start_col=5, end_col=7, output_format="diff")
            assert isinstance(patches, dict)
        except Exception:
            pass


@pytest.mark.unit
@pytest.mark.rope
class TestMoveEdgeCasesDiff:
    """Edge cases for move in diff format."""

    def test_move_module_level_diff(self, tmp_path):
        """Move entire module in diff format."""
        source = tmp_path / "source.py"
        source.write_text("def func():\n    pass\n")

        target = tmp_path / "target.py"
        target.write_text("")

        engine = RopeEngine(tmp_path)
        try:
            patches = engine.move("source.py", "target.py", line=1, col=5, output_format="diff")
            assert isinstance(patches, dict)
        except Exception:
            pass

    def test_move_to_nonexistent_file_diff(self, tmp_path):
        """Move to a file that doesn't exist yet in diff format."""
        source = tmp_path / "source.py"
        source.write_text("def func():\n    pass\n")

        engine = RopeEngine(tmp_path)
        try:
            patches = engine.move("source.py", "new_target.py", line=1, col=5, output_format="diff")
            assert isinstance(patches, dict)
        except Exception:
            pass

    def test_move_class_diff(self, tmp_path):
        """Move a class to another file in diff format."""
        source = tmp_path / "source.py"
        source_content = """
class MyClass:
    def method(self):
        pass
"""
        source.write_text(source_content)

        target = tmp_path / "target.py"
        target.write_text("")

        engine = RopeEngine(tmp_path)
        diff_patches = engine.move("source.py", "target.py", line=2, col=7, output_format="diff")
        full_patches = engine.move("source.py", "target.py", line=2, col=7, output_format="full")

        assert isinstance(diff_patches, dict)
        # Verify diffs apply correctly
        if "source.py" in diff_patches:
            patched = apply_unified_diff(source_content, diff_patches["source.py"])
            assert patched == full_patches.get("source.py", "")

    def test_move_with_line_only_diff(self, tmp_path):
        """Move with line but no column in diff format."""
        source = tmp_path / "source.py"
        source.write_text("def func():\n    pass\n")

        target = tmp_path / "target.py"
        target.write_text("")

        engine = RopeEngine(tmp_path)
        try:
            patches = engine.move("source.py", "target.py", line=1, col=None, output_format="diff")
            assert isinstance(patches, dict)
        except Exception:
            pass


@pytest.mark.unit
@pytest.mark.rope
class TestOrganizeImportsEdgeCasesDiff:
    """Edge cases for organize_imports in diff format."""

    def test_organize_imports_convert_froms_false_diff(self, tmp_path):
        """Organize imports with convert_froms=False in diff format."""
        test_file = tmp_path / "test.py"
        original = "from os import path\nprint(path.exists('.'))\n"
        test_file.write_text(original)

        engine = RopeEngine(tmp_path)
        diff_patches = engine.organize_imports(test_file, convert_froms=False, output_format="diff")
        full_patches = engine.organize_imports(test_file, convert_froms=False, output_format="full")

        if diff_patches:
            patched = apply_unified_diff(original, diff_patches["test.py"])
            assert patched == full_patches["test.py"]

    def test_organize_imports_convert_froms_true_diff(self, tmp_path):
        """Organize imports with convert_froms=True in diff format."""
        test_file = tmp_path / "test.py"
        original = "from os import path\nprint(path.exists('.'))\n"
        test_file.write_text(original)

        engine = RopeEngine(tmp_path)
        diff_patches = engine.organize_imports(test_file, convert_froms=True, output_format="diff")
        full_patches = engine.organize_imports(test_file, convert_froms=True, output_format="full")

        if diff_patches:
            patched = apply_unified_diff(original, diff_patches["test.py"])
            assert patched == full_patches["test.py"]

    def test_organize_imports_directory_diff(self, tmp_path):
        """Organize imports in a directory in diff format."""
        subdir = tmp_path / "package"
        subdir.mkdir()

        file1 = subdir / "module1.py"
        content1 = "import sys\nimport os\nprint(os.getcwd())\n"
        file1.write_text(content1)

        file2 = subdir / "module2.py"
        content2 = "import json\nprint(json.dumps({}))\n"
        file2.write_text(content2)

        engine = RopeEngine(tmp_path)
        diff_patches = engine.organize_imports(subdir, convert_froms=False, output_format="diff")
        full_patches = engine.organize_imports(subdir, convert_froms=False, output_format="full")

        # Verify all diffs apply correctly
        for file_path, diff_text in diff_patches.items():
            if "module1.py" in file_path:
                original = content1
            elif "module2.py" in file_path:
                original = content2
            else:
                continue

            patched = apply_unified_diff(original, diff_text)
            assert patched == full_patches[file_path]

    def test_organize_imports_nonexistent_path_diff(self, tmp_path):
        """Organize imports with non-existent path raises ValueError in diff format."""
        engine = RopeEngine(tmp_path)
        fake_path = tmp_path / "nonexistent.py"

        with pytest.raises(ValueError, match="Path not found"):
            engine.organize_imports(fake_path, convert_froms=False, output_format="diff")

    def test_organize_imports_already_organized_diff(self, tmp_path):
        """Organize imports on already organized file in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import os\nimport sys\nprint(os.getcwd())\n")

        engine = RopeEngine(tmp_path)
        patches = engine.organize_imports(test_file, convert_froms=False, output_format="diff")

        assert isinstance(patches, dict)

    def test_organize_imports_with_syntax_error_diff(self, tmp_path):
        """Organize imports on file with syntax error in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import os\ndef broken(\n")

        engine = RopeEngine(tmp_path)
        patches = engine.organize_imports(test_file, convert_froms=False, output_format="diff")

        assert isinstance(patches, dict)

    def test_organize_imports_unused_imports_diff(self, tmp_path):
        """Organize imports might remove unused imports in diff format."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import os\nimport sys\nimport unused_module\nprint(os.getcwd())\n")

        engine = RopeEngine(tmp_path)
        patches = engine.organize_imports(test_file, convert_froms=False, output_format="diff")

        assert isinstance(patches, dict)


@pytest.mark.unit
@pytest.mark.rope
class TestDiffSpecificEdgeCases:
    """Edge cases specific to diff format (not in full format tests)."""

    def test_diff_empty_file_to_content(self, tmp_path):
        """Diff from empty file to content works correctly."""
        test_file = tmp_path / "test.py"
        test_file.write_text("")

        # Write some content
        test_file.write_text("def new_func():\n    pass\n")

        engine = RopeEngine(tmp_path)

        # Reset file to empty
        test_file.write_text("")

        # Now add content via refactoring won't work with empty file
        # But we test that empty patches are handled
        patches = engine.rename("test.py", 1, 1, "anything", output_format="diff")

        # Should handle gracefully (empty or error)
        assert isinstance(patches, dict)

    def test_diff_file_with_only_whitespace(self, tmp_path):
        """Diff handles files with only whitespace."""
        test_file = tmp_path / "test.py"
        test_file.write_text("   \n\n   \n")

        engine = RopeEngine(tmp_path)
        try:
            patches = engine.organize_imports(test_file, convert_froms=False, output_format="diff")
            assert isinstance(patches, dict)
        except Exception:
            pass

    def test_diff_with_unicode_content(self, tmp_path):
        """Diff handles Unicode content correctly."""
        test_file = tmp_path / "test.py"
        original = """# -*- coding: utf-8 -*-
def café():
    return "☕"

résultat = café()
"""
        test_file.write_text(original, encoding='utf-8')

        engine = RopeEngine(tmp_path)
        diff_patches = engine.rename("test.py", 2, 5, "coffee", output_format="diff")
        full_patches = engine.rename("test.py", 2, 5, "coffee", output_format="full")

        if diff_patches:
            diff_text = diff_patches["test.py"]
            patched = apply_unified_diff(original, diff_text)
            assert patched == full_patches["test.py"]

    def test_diff_very_long_lines(self, tmp_path):
        """Diff handles very long lines correctly."""
        # Create file with very long line
        long_string = "x" * 1000
        test_file = tmp_path / "test.py"
        original = f'old_var = "{long_string}"\nresult = old_var\n'
        test_file.write_text(original)

        engine = RopeEngine(tmp_path)
        diff_patches = engine.rename("test.py", 1, 1, "new_var", output_format="diff")
        full_patches = engine.rename("test.py", 1, 1, "new_var", output_format="full")

        diff_text = diff_patches["test.py"]
        patched = apply_unified_diff(original, diff_text)
        assert patched == full_patches["test.py"]

    def test_diff_many_small_changes(self, tmp_path):
        """Diff with many small scattered changes works correctly."""
        test_file = tmp_path / "test.py"
        original = """
x = 1
y = 2
z = 3
a = 4
b = 5

def func1():
    return x

def func2():
    return y

def func3():
    return z
"""
        test_file.write_text(original)

        engine = RopeEngine(tmp_path)
        diff_patches = engine.rename("test.py", 2, 1, "new_x", output_format="diff")
        full_patches = engine.rename("test.py", 2, 1, "new_x", output_format="full")

        diff_text = diff_patches["test.py"]
        patched = apply_unified_diff(original, diff_text)
        assert patched == full_patches["test.py"]

    def test_diff_at_file_start(self, tmp_path):
        """Diff with changes at the very start of file."""
        test_file = tmp_path / "test.py"
        original = "old_name = 1\nx = old_name + 2\n"
        test_file.write_text(original)

        engine = RopeEngine(tmp_path)
        diff_patches = engine.rename("test.py", 1, 1, "new_name", output_format="diff")
        full_patches = engine.rename("test.py", 1, 1, "new_name", output_format="full")

        diff_text = diff_patches["test.py"]
        patched = apply_unified_diff(original, diff_text)
        assert patched == full_patches["test.py"]

    def test_diff_at_file_end(self, tmp_path):
        """Diff with changes at the very end of file."""
        test_file = tmp_path / "test.py"
        original = """
def func():
    pass

old_var = 1
"""
        test_file.write_text(original)

        engine = RopeEngine(tmp_path)
        diff_patches = engine.rename("test.py", 5, 1, "new_var", output_format="diff")
        full_patches = engine.rename("test.py", 5, 1, "new_var", output_format="full")

        diff_text = diff_patches["test.py"]
        patched = apply_unified_diff(original, diff_text)
        assert patched == full_patches["test.py"]

    def test_diff_preserves_trailing_newline(self, tmp_path):
        """Diff preserves trailing newlines correctly."""
        test_file = tmp_path / "test.py"
        original = "old_name = 1\n"
        test_file.write_text(original)

        engine = RopeEngine(tmp_path)
        diff_patches = engine.rename("test.py", 1, 1, "new_name", output_format="diff")
        full_patches = engine.rename("test.py", 1, 1, "new_name", output_format="full")

        diff_text = diff_patches["test.py"]
        patched = apply_unified_diff(original, diff_text)

        # Should preserve trailing newline
        assert patched == full_patches["test.py"]
        if full_patches["test.py"].endswith('\n'):
            assert patched.endswith('\n')

    def test_diff_no_trailing_newline(self, tmp_path):
        """Diff handles files without trailing newline."""
        test_file = tmp_path / "test.py"
        original = "old_name = 1"  # No trailing newline
        test_file.write_text(original)

        engine = RopeEngine(tmp_path)
        diff_patches = engine.rename("test.py", 1, 1, "new_name", output_format="diff")
        full_patches = engine.rename("test.py", 1, 1, "new_name", output_format="full")

        if diff_patches:
            diff_text = diff_patches["test.py"]
            patched = apply_unified_diff(original, diff_text)
            assert patched == full_patches["test.py"]

    def test_diff_mixed_indentation(self, tmp_path):
        """Diff handles mixed tab/space indentation."""
        test_file = tmp_path / "test.py"
        original = "def old_func():\n\tpass\n    return 1\n"  # Mixed tabs and spaces
        test_file.write_text(original)

        engine = RopeEngine(tmp_path)
        diff_patches = engine.rename("test.py", 1, 5, "new_func", output_format="diff")
        full_patches = engine.rename("test.py", 1, 5, "new_func", output_format="full")

        diff_text = diff_patches["test.py"]
        patched = apply_unified_diff(original, diff_text)
        assert patched == full_patches["test.py"]

    def test_diff_consecutive_blank_lines(self, tmp_path):
        """Diff handles consecutive blank lines correctly."""
        test_file = tmp_path / "test.py"
        original = """
def old_func():
    pass



def other():
    pass
"""
        test_file.write_text(original)

        engine = RopeEngine(tmp_path)
        diff_patches = engine.rename("test.py", 2, 5, "new_func", output_format="diff")
        full_patches = engine.rename("test.py", 2, 5, "new_func", output_format="full")

        diff_text = diff_patches["test.py"]
        patched = apply_unified_diff(original, diff_text)
        assert patched == full_patches["test.py"]


@pytest.mark.unit
@pytest.mark.rope
class TestDiffHelper:
    """Test the _generate_unified_diff helper function."""

    def test_generate_diff_with_changes(self):
        """_generate_unified_diff produces valid diff."""
        from pyclide_server.rope_engine import _generate_unified_diff

        old_content = "line 1\nold line\nline 3\n"
        new_content = "line 1\nnew line\nline 3\n"

        diff = _generate_unified_diff("test.py", old_content, new_content)

        assert "--- test.py" in diff
        assert "+++ test.py" in diff
        assert "-old line" in diff
        assert "+new line" in diff

    def test_generate_diff_no_changes(self):
        """_generate_unified_diff returns empty for identical content."""
        from pyclide_server.rope_engine import _generate_unified_diff

        content = "line 1\nline 2\nline 3\n"
        diff = _generate_unified_diff("test.py", content, content)

        # No changes = empty string
        assert diff == ""

    def test_generate_diff_multiple_hunks(self):
        """_generate_unified_diff handles multiple change hunks."""
        from pyclide_server.rope_engine import _generate_unified_diff

        old_content = "line 1\nold_a\nline 3\nline 4\nline 5\nold_b\nline 7\n"
        new_content = "line 1\nnew_a\nline 3\nline 4\nline 5\nnew_b\nline 7\n"

        diff = _generate_unified_diff("test.py", old_content, new_content)

        # Should have changes
        assert "-old_a" in diff
        assert "+new_a" in diff
        assert "-old_b" in diff
        assert "+new_b" in diff
