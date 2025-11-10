"""
Rope integration for refactoring operations.
Extracted from pyclide.py for server use.
"""

import difflib
import pathlib
import re
from typing import Dict, List, Any, Literal

from rope.base.project import Project
from rope.base.libutils import path_to_resource
from rope.refactor.rename import Rename
from rope.refactor.extract import ExtractMethod, ExtractVariable
from rope.refactor.move import create_move
from rope.refactor.importutils import ImportOrganizer
from rope.refactor import occurrences

from .utils import byte_offset, rel_to


def _generate_unified_diff(old_path: str, old_content: str, new_content: str) -> str:
    """
    Generate unified diff between old and new content.

    Args:
        old_path: File path for diff headers
        new_path: File path for diff headers
        old_content: Original file content
        new_content: Modified file content

    Returns:
        Unified diff string, or empty string if no changes
    """
    if old_content == new_content:
        return ""

    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=old_path,
        tofile=old_path,
        lineterm=''
    )

    # Join with newlines to create properly formatted diff
    return '\n'.join(diff)


class RopeEngine:
    """
    Thin stateful wrapper around Rope's Project to enable:
    - occurrences (semantic references within rename scope)
    - rename (semantic refactor)
    - extract_method / extract_variable
    - move (symbols or modules)
    - organize_imports (normalize imports)

    Rope computes scopes and updates imports/usages semantically where possible.
    """

    def __init__(self, root: pathlib.Path):
        self.root = root.resolve()
        # Configure Rope to ignore syntax errors in project files
        self.project = Project(str(self.root), ignore_syntax_errors=True)

    def _res(self, file_path: str):
        """
        Resolve a project resource for a given path (relative to `root` or absolute).
        This is Rope's abstraction over a file in the project.
        """
        return path_to_resource(self.project, str((self.root / file_path).resolve()))

    def occurrences(self, file_path: str, line: int, col: int) -> List[Dict[str, Any]]:
        """
        Return semantic occurrences (reference-like results) for the symbol at (line, col).
        """
        res = self._res(file_path)
        src = res.read()
        off = byte_offset(src, line, col)

        # Create a Rename instance to get access to old_name and old_pyname
        renamer = Rename(self.project, res, off)

        # Create an occurrences finder
        finder = occurrences.create_finder(
            self.project,
            renamer.old_name,
            renamer.old_pyname,
            instance=renamer.old_instance,
        )

        # Find all occurrences
        out: List[Dict[str, Any]] = []
        pymodule = self.project.get_pymodule(res)
        for o in finder.find_occurrences(resource=res, pymodule=pymodule):
            # Convert Rope offsets back to 1-based (line, column)
            start, end = o.get_word_range()
            full_text = o.resource.read()
            lines_before = full_text[:start].splitlines()
            lineno = len(lines_before)
            if lineno > 0:
                column = len(lines_before[-1]) + 1
            else:
                column = start + 1

            out.append({
                "path": rel_to(self.root, pathlib.Path(o.resource.real_path)),
                "line": lineno,
                "column": column,
            })
        return out

    def rename(self, file_path: str, line: int, col: int, new_name: str, output_format: Literal["diff", "full"] = "diff") -> Dict[str, str]:
        """
        Compute a semantic rename for the symbol at (line, col).

        Args:
            file_path: Path to the file containing the symbol
            line: 1-based line number
            col: 1-based column number
            new_name: New name for the symbol
            output_format: "diff" returns unified diffs, "full" returns complete file contents

        Returns:
            Mapping of {relative_file_path: diff_or_full_content}
        """
        res = self._res(file_path)
        src = res.read()
        off = byte_offset(src, line, col)
        changes = Rename(self.project, res, off).get_changes(new_name)
        patches: Dict[str, str] = {}
        for ch in changes.changes:
            r = ch.resource
            new_text = ch.new_contents.decode() if isinstance(ch.new_contents, (bytes, bytearray)) else ch.new_contents
            rel_path = rel_to(self.root, pathlib.Path(r.real_path))

            if output_format == "diff":
                old_text = r.read()
                diff = _generate_unified_diff(rel_path, old_text, new_text)
                if diff:  # Only include files with changes
                    patches[rel_path] = diff
            else:
                patches[rel_path] = new_text
        return patches

    def extract_method(self, file_path: str, start_line: int, end_line: int, new_name: str, output_format: Literal["diff", "full"] = "diff") -> Dict[str, str]:
        """
        Extract code block into a new method.

        Args:
            file_path: Path to the file
            start_line: Starting line number (1-based)
            end_line: Ending line number (1-based)
            new_name: Name for the new method
            output_format: "diff" returns unified diffs, "full" returns complete file contents

        Returns:
            Mapping of {relative_file_path: diff_or_full_content}
        """
        res = self._res(file_path)
        src = res.read()
        start = byte_offset(src, start_line, 1)
        end = byte_offset(src, end_line + 1, 1) if end_line >= start_line else start
        changes = ExtractMethod(self.project, res, start, end).get_changes(new_name)
        patches: Dict[str, str] = {}
        for ch in changes.changes:
            r = ch.resource
            new_text = ch.new_contents.decode() if isinstance(ch.new_contents, (bytes, bytearray)) else ch.new_contents
            rel_path = rel_to(self.root, pathlib.Path(r.real_path))

            if output_format == "diff":
                old_text = r.read()
                diff = _generate_unified_diff(rel_path, old_text, new_text)
                if diff:
                    patches[rel_path] = diff
            else:
                patches[rel_path] = new_text
        return patches

    def extract_variable(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        new_name: str,
        start_col: int = None,
        end_col: int = None,
        output_format: Literal["diff", "full"] = "diff"
    ) -> Dict[str, str]:
        """
        Extract expression into a new variable.

        Args:
            file_path: Path to the file
            start_line: Starting line number (1-based)
            end_line: Ending line number (1-based)
            new_name: Name for the new variable
            start_col: Optional starting column (1-based)
            end_col: Optional ending column (1-based)
            output_format: "diff" returns unified diffs, "full" returns complete file contents

        Returns:
            Mapping of {relative_file_path: diff_or_full_content}
        """
        res = self._res(file_path)
        src = res.read()

        # Determine start offset
        if start_col is None:
            start = byte_offset(src, start_line, 1)
        else:
            start = byte_offset(src, start_line, start_col)

        # Determine end offset
        if end_col is None:
            end = byte_offset(src, end_line + 1, 1)
        else:
            end = byte_offset(src, end_line, end_col)

        changes = ExtractVariable(self.project, res, start, end).get_changes(new_name)
        patches: Dict[str, str] = {}
        for ch in changes.changes:
            r = ch.resource
            new_text = ch.new_contents.decode() if isinstance(ch.new_contents, (bytes, bytearray)) else ch.new_contents
            rel_path = rel_to(self.root, pathlib.Path(r.real_path))

            if output_format == "diff":
                old_text = r.read()
                diff = _generate_unified_diff(rel_path, old_text, new_text)
                if diff:
                    patches[rel_path] = diff
            else:
                patches[rel_path] = new_text
        return patches

    def move(self, file_path: str, target_file: str, line: int = None, col: int = None, output_format: Literal["diff", "full"] = "diff") -> Dict[str, str]:
        """
        Move a symbol or module.

        Args:
            file_path: Source file path
            target_file: Destination file path
            line: Optional 1-based line number for symbol move
            col: Optional 1-based column number for symbol move
            output_format: "diff" returns unified diffs, "full" returns complete file contents

        If line and col are provided, moves the symbol at that position.
        If not provided, moves the entire module.

        Returns:
            Mapping of {relative_file_path: diff_or_full_content}
        """
        src_res = self._res(file_path)
        dst_res = self._res(target_file)

        if line is not None and col is not None:
            # Symbol-level move using line/col
            src_text = src_res.read()
            offset = byte_offset(src_text, line, col)
        else:
            # Module-level move
            offset = 0

        mover = create_move(self.project, src_res, offset)
        changes = mover.get_changes(dst_res)

        patches: Dict[str, str] = {}
        for ch in changes.changes:
            r = ch.resource
            new_text = ch.new_contents.decode() if isinstance(ch.new_contents, (bytes, bytearray)) else ch.new_contents
            rel_path = rel_to(self.root, pathlib.Path(r.real_path))

            if output_format == "diff":
                old_text = r.read()
                diff = _generate_unified_diff(rel_path, old_text, new_text)
                if diff:
                    patches[rel_path] = diff
            else:
                patches[rel_path] = new_text
        return patches

    def organize_imports(self, path: pathlib.Path, convert_froms: bool, output_format: Literal["diff", "full"] = "diff") -> Dict[str, str]:
        """
        Normalize/organize imports using Rope.

        Args:
            path: File or directory path
            convert_froms: Whether to convert from imports
            output_format: "diff" returns unified diffs, "full" returns complete file contents

        Returns:
            Mapping of {relative_file_path: diff_or_full_content}
        """
        org = ImportOrganizer(self.project)
        targets = []
        if path.is_dir():
            targets = [q for q in path.rglob("*.py")]
        else:
            if not path.exists():
                raise ValueError(f"Path not found: {path}")
            targets = [path]

        patches: Dict[str, str] = {}
        for f in targets:
            res = path_to_resource(self.project, str(f.resolve()))
            src = res.read()

            try:
                changes = org.organize_imports(res)
                new_src = src

                if changes and changes.changes:
                    for ch in changes.changes:
                        if ch.resource == res:
                            new_src = ch.new_contents
                            if isinstance(new_src, bytes):
                                new_src = new_src.decode('utf-8')
                            break

                if convert_froms:
                    changes = org.froms_to_imports(res)
                    if changes and changes.changes:
                        for ch in changes.changes:
                            if ch.resource == res:
                                new_src = ch.new_contents
                                if isinstance(new_src, bytes):
                                    new_src = new_src.decode('utf-8')
                                break

                if new_src != src:
                    rel_path = rel_to(self.root, f)
                    if output_format == "diff":
                        diff = _generate_unified_diff(rel_path, src, new_src)
                        if diff:
                            patches[rel_path] = diff
                    else:
                        patches[rel_path] = new_src
            except Exception:
                pass

        return patches
