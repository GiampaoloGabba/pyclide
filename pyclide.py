#!/usr/bin/env python3
"""
PyCLIDE: Python Command-Line IDE
A single CLI that exposes IDE-like semantic code retrieval and refactoring
features for Python codebases, designed to be easy for an agent to drive.

Core engines:
- Jedi (definitions, references, completions/goto).
- Rope (semantic refactorings: rename, extract method/variable, move, occurrences).
Optional extras:
- ast-grep (AST-based codemod for mass search/replace).

All commands can return JSON to simplify agent parsing. Mutating commands support
previewing patch contents and applying atomically upon confirmation (or --force).
"""

from __future__ import annotations

import ast
import difflib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import List, Dict, Any

import typer

# --------------------------------------------------------------------------------------
# Version
# --------------------------------------------------------------------------------------

VERSION = "1.0.0"

# --------------------------------------------------------------------------------------
# CLI bootstrap
# --------------------------------------------------------------------------------------

app = typer.Typer(
    help=(
        "PyCLIDE: Python Command-Line IDE\n"
        "Semantic code search & refactor for Python (Jedi + Rope + extras)\n"
        "Use --help on any subcommand for details."
    )
)

def version_callback(value: bool):
    """
    Callback for --version flag. Prints version and exits.
    """
    if value:
        typer.echo(f"PyCLIDE version {VERSION}")
        raise typer.Exit()

@app.callback()
def main_callback(
    version: bool = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit."
    )
):
    """
    Global options callback. Handles --version before any subcommand runs.
    """
    pass

# Track missing dynamic imports so the CLI can degrade gracefully and explain what to install.
_missing: Dict[str, str] = {}
try:
    import jedi  # type: ignore
except Exception as e:
    _missing["jedi"] = f"{e}"

try:
    from rope.base.project import Project  # type: ignore
    from rope.base.libutils import path_to_resource  # type: ignore
    from rope.refactor.rename import Rename  # type: ignore
    from rope.refactor.extract import ExtractMethod, ExtractVariable  # type: ignore
    from rope.refactor.move import create_move  # type: ignore
    from rope.refactor.importutils import ImportOrganizer  # type: ignore
except Exception as e:
    _missing["rope"] = f"{e}"

# --------------------------------------------------------------------------------------
# Small utility helpers
# --------------------------------------------------------------------------------------

def eprint(*a, **k) -> None:
    """Print to stderr (convenience)."""
    print(*a, file=sys.stderr, **k)

def ensure(cond: bool, msg: str):
    """
    Guard that exits the CLI with a helpful error message when `cond` is False.
    Designed for predictable control flow from an agent.
    """
    if not cond:
        typer.echo(msg, err=True)
        raise typer.Exit(code=2)

def read_text(p: pathlib.Path) -> str:
    """Read UTF-8 text from a file."""
    return p.read_text(encoding="utf-8")

def write_text_atomic(p: pathlib.Path, content: str) -> None:
    """
    Atomically write UTF-8 text to a file by writing to a temp path and renaming.
    This minimizes races and prevents partial writes.
    """
    tmp = p.with_suffix(p.suffix + ".pyclide.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(p)

def rel_to(root: pathlib.Path, path: pathlib.Path) -> str:
    """Return a path relative to root if possible, else the absolute path as string."""
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)

def byte_offset(text: str, line_1based: int, col_1based: int) -> int:
    """
    Convert 1-based (line, col) to a 0-based byte offset for Rope.
    Rope APIs use a single offset in the file buffer; many agent UIs use line/col.
    """
    lines = text.splitlines(True)
    return sum(len(l) for l in lines[:max(0, line_1based - 1)]) + max(0, col_1based - 1)

def maybe_json(data: Any, json_out: bool) -> None:
    """
    Print structured JSON for agent consumption, or a human-friendly representation.
    Use JSON for predictable parsing by a coding agent.
    """
    if json_out:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if isinstance(data, dict):
            for k, v in data.items():
                typer.echo(f"[{k}]\n{v}\n{'-'*60}")
        elif isinstance(data, list):
            for row in data:
                typer.echo(json.dumps(row, ensure_ascii=False))
        else:
            typer.echo(str(data))

def confirm_apply(force: bool) -> bool:
    """
    Ask for confirmation before writing patches to disk unless --force is used.
    Agents can set --force to skip interactivity.
    """
    if force:
        return True
    typer.echo("Apply changes to files? [y/N] ", nl=False)
    ans = sys.stdin.readline().strip().lower()
    return ans in ("y", "yes")

# --------------------------------------------------------------------------------------
# Rope integration (project-aware, refactorings, occurrences)
# --------------------------------------------------------------------------------------

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
        if "rope" in _missing:
            raise RuntimeError(f"Rope not available: install with `pip install rope`.\n{_missing['rope']}")
        self.root = root.resolve()
        # Configure Rope to ignore syntax errors in project files
        # This allows Rope to work on valid files even if some files have syntax errors
        self.project = Project(str(self.root), ignore_syntax_errors=True)

    def _res(self, file_path: str):
        """
        Resolve a project resource for a given path (relative to `root` or absolute).
        This is Rope's abstraction over a file in the project.
        """
        return path_to_resource(self.project, str((self.root / file_path).resolve()))

    # ---------------- Retrieval ----------------

    def occurrences(self, file_path: str, line: int, col: int) -> List[Dict[str, Any]]:
        """
        Return semantic occurrences (reference-like results) for the symbol at (line, col)
        in `file_path`. Uses Rope's occurrences finder as a robust proxy for
        "find references" restricted to the renaming scope Rope understands.
        """
        from rope.refactor import occurrences

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
            # Convert Rope offsets back to 1-based (line, column) for consistency.
            start, end = o.get_word_range()
            # Calculate line and column from offset
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

    # ---------------- Editing (refactors) ----------------

    def rename(self, file_path: str, line: int, col: int, new_name: str) -> Dict[str, str]:
        """
        Compute a semantic rename for the symbol at (line, col) in `file_path`.
        Returns a mapping: {relative_file_path: new_file_contents} WITHOUT writing to disk.
        The caller is responsible for previewing and applying the patches.
        """
        res = self._res(file_path)
        src = res.read()
        off = byte_offset(src, line, col)
        changes = Rename(self.project, res, off).get_changes(new_name)
        patches: Dict[str, str] = {}
        for ch in changes.changes:
            r = ch.resource
            new_text = ch.new_contents.decode() if hasattr(ch, "new_contents") and isinstance(ch.new_contents, (bytes, bytearray)) else ch.new_contents
            patches[rel_to(self.root, pathlib.Path(r.real_path))] = new_text
        return patches

    def extract_method(self, file_path: str, start_line: int, end_line: int, new_name: str) -> Dict[str, str]:
        """
        Extract the code block spanning [start_line, end_line] in `file_path` into a new method
        named `new_name`. Returns in-memory patches (no file I/O).
        """
        res = self._res(file_path)
        src = res.read()
        start = byte_offset(src, start_line, 1)
        end = byte_offset(src, end_line + 1, 1) if end_line >= start_line else start
        changes = ExtractMethod(self.project, res, start, end).get_changes(new_name)
        patches: Dict[str, str] = {}
        for ch in changes.changes:
            r = ch.resource
            new_text = ch.new_contents.decode() if hasattr(ch, "new_contents") and isinstance(ch.new_contents, (bytes, bytearray)) else ch.new_contents
            patches[rel_to(self.root, pathlib.Path(r.real_path))] = new_text
        return patches

    def extract_variable(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        new_name: str,
        start_col: int = None,
        end_col: int = None
    ) -> Dict[str, str]:
        """
        Extract a code expression into a new variable `new_name`.
        Returns in-memory patches (no file I/O).

        Args:
            file_path: Path to the file
            start_line: Starting line (1-based)
            end_line: Ending line (1-based)
            new_name: Name for the new variable
            start_col: Optional starting column (1-based). If None, starts from beginning of line.
            end_col: Optional ending column (1-based). If None, goes to end of line.

        Behavior:
            - If neither start_col nor end_col are provided: extracts entire line(s)
            - If only start_col is provided: extracts from start_col to end of end_line
            - If only end_col is provided: extracts from beginning of start_line to end_col
            - If both are provided: extracts precise selection from start_line:start_col to end_line:end_col
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
            # Go to end of line: start of next line
            end = byte_offset(src, end_line + 1, 1)
        else:
            end = byte_offset(src, end_line, end_col)

        changes = ExtractVariable(self.project, res, start, end).get_changes(new_name)
        patches: Dict[str, str] = {}
        for ch in changes.changes:
            r = ch.resource
            new_text = ch.new_contents.decode() if hasattr(ch, "new_contents") and isinstance(ch.new_contents, (bytes, bytearray)) else ch.new_contents
            patches[rel_to(self.root, pathlib.Path(r.real_path))] = new_text
        return patches

    def move(self, source_spec: str, target_file: str) -> Dict[str, str]:
        """
        Move a symbol or an entire module and update references accordingly.
        - `source_spec` format:
            - 'path/to/file.py::SymbolName' to move a top-level function/class within that file
            - 'path/to/file.py' to move the entire module
        - `target_file` is the destination file path.

        Returns in-memory patches (no file I/O).
        """
        # Parse 'file.py::Symbol' or 'file.py'
        if "::" in source_spec:
            file_path, symbol = source_spec.split("::", 1)
        else:
            file_path, symbol = source_spec, None

        # Build Rope resources
        src_res = self._res(file_path)
        dst_res = self._res(target_file)

        # Determine an offset for the symbol; for whole-module moves, offset=0 is fine.
        if symbol:
            src_text = src_res.read()
            # Simple heuristic to find first occurrence of the symbol token; sufficient for top-level decls.
            import re
            m = re.search(rf"\b{re.escape(symbol)}\b", src_text)
            ensure(m is not None, f"Symbol '{symbol}' not found in {file_path}")
            offset = m.start()
        else:
            offset = 0

        mover = create_move(self.project, src_res, offset)
        changes = mover.get_changes(dst_res)

        patches: Dict[str, str] = {}
        for ch in changes.changes:
            r = ch.resource
            new_text = ch.new_contents.decode() if hasattr(ch, "new_contents") and isinstance(ch.new_contents, (bytes, bytearray)) else ch.new_contents
            patches[rel_to(self.root, pathlib.Path(r.real_path))] = new_text
        return patches

    def organize_imports(self, path: pathlib.Path, convert_froms: bool) -> Dict[str, str]:
        """
        Normalize/organize imports using Rope's ImportOrganizer across a file or directory.
        If `convert_froms` is true, attempt to convert `from X import Y` patterns into `import X`
        where feasible, qualifying uses accordingly.

        Returns in-memory patches for each file that would change.
        """
        org = ImportOrganizer(self.project)
        targets = []
        if path.is_dir():
            targets = [q for q in path.rglob("*.py")]
        else:
            ensure(path.exists(), f"Path not found: {path}")
            targets = [path]

        patches: Dict[str, str] = {}
        for f in targets:
            res = path_to_resource(self.project, str(f.resolve()))
            src = res.read()

            # Try to organize imports
            try:
                changes = org.organize_imports(res)
                new_src = src  # Default to original

                # organize_imports returns a ChangeSet with changes for the file
                if changes and changes.changes:
                    # Find the change for our resource
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
                    patches[rel_to(self.root, f)] = new_src
            except Exception:
                # If organize_imports fails, skip this file
                pass

        return patches

# --------------------------------------------------------------------------------------
# Jedi helpers (definitions, references)
# --------------------------------------------------------------------------------------

def jedi_script(root: pathlib.Path, file_path: str):
    """
    Construct a Jedi Script for a given file. Jedi analyzes the file/module to
    provide definitions/references/etc. The file must exist on disk.
    """
    if "jedi" in _missing:
        raise RuntimeError(f"Jedi not available: install with `pip install jedi`.\n{_missing['jedi']}")
    path = str((root / file_path).resolve())
    return jedi.Script(path=path)  # type: ignore

def jedi_to_locations(defs) -> List[Dict[str, Any]]:
    """
    Convert Jedi definitions/references to a normalized location dict:
    {path, line, column, name, type}
    """
    out: List[Dict[str, Any]] = []
    for d in defs:
        if not getattr(d, "module_path", None) or getattr(d, "line", None) is None:
            continue
        out.append({
            "path": str(d.module_path),
            "line": d.line,
            "column": d.column or 1,
            "name": d.name,
            "type": d.type,
        })
    return out

# --------------------------------------------------------------------------------------
# Patch preview & apply
# --------------------------------------------------------------------------------------

def show_and_apply_patches(root: pathlib.Path, patches: Dict[str, str], force: bool, json_out: bool) -> None:
    """
    Display a unified diff for each changed file (when --no-json),
    or emit the patch mapping as JSON (when --json). Then, optionally apply.
    """
    if json_out:
        maybe_json({"patches": patches}, True)
    else:
        for rel, new_text in patches.items():
            p = (root / rel).resolve()
            old = read_text(p)
            diff = difflib.unified_diff(
                old.splitlines(), new_text.splitlines(),
                fromfile=str(rel) + ":old", tofile=str(rel) + ":new",
                lineterm=""
            )
            typer.echo("\n".join(diff))
    if not patches:
        eprint("No changes.")
        return
    if confirm_apply(force):
        for rel, new_text in patches.items():
            p = (root / rel).resolve()
            write_text_atomic(p, new_text)
        eprint(f"✅ Applied changes to {len(patches)} file(s).")
    else:
        eprint("❎ Changes NOT applied.")

# --------------------------------------------------------------------------------------
# Commands: Navigation (Jedi)
# --------------------------------------------------------------------------------------

@app.command()
def defs(
        file: str = typer.Argument(..., help="Path to the Python file."),
        line: int = typer.Argument(..., help="1-based line number."),
        col: int = typer.Argument(..., help="1-based column number."),
        root: str = typer.Option(".", help="Project root for resolution."),
        json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON."),
):
    """
    Jump to definition using Jedi. If multiple targets exist, returns all candidates.
    Useful for 'go to definition' behavior in agents.
    """
    ensure("jedi" not in _missing, "Jedi not installed. Run: pip install jedi")
    scr = jedi_script(pathlib.Path(root), file)
    res = scr.goto(line, col) or scr.infer(line, col)
    maybe_json(jedi_to_locations(res), json_out)

@app.command()
def refs(
        file: str = typer.Argument(..., help="Path to the Python file."),
        line: int = typer.Argument(..., help="1-based line number."),
        col: int = typer.Argument(..., help="1-based column number."),
        root: str = typer.Option(".", help="Project root for resolution."),
        json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON."),
):
    """
    Find references (usages) using Jedi. Note this can include definitions unless filtered.
    For more rename-safe occurrences, prefer the `occurrences` command (Rope-based).
    """
    ensure("jedi" not in _missing, "Jedi not installed. Run: pip install jedi")
    scr = jedi_script(pathlib.Path(root), file)
    res = scr.get_references(line, col, include_builtins=False)
    maybe_json(jedi_to_locations(res), json_out)

@app.command()
def hover(
        file: str = typer.Argument(..., help="Path to the Python file."),
        line: int = typer.Argument(..., help="1-based line number."),
        col: int = typer.Argument(..., help="1-based column number."),
        root: str = typer.Option(".", help="Project root for resolution."),
        json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON."),
):
    """
    Get quick information about the symbol at (line, col) using Jedi.
    Returns type, signature, and docstring without navigating away.
    Useful for agents to understand code context at a cursor position.
    """
    ensure("jedi" not in _missing, "Jedi not installed. Run: pip install jedi")
    scr = jedi_script(pathlib.Path(root), file)
    names = scr.infer(line, col)

    results = []
    for name in names:
        info = {
            "name": name.name,
            "type": name.type,
            "full_name": name.full_name or name.name,
        }

        # Add signature if available (for functions/methods)
        try:
            sigs = name.get_signatures()
            if sigs:
                # Format signature as "func_name(params) -> return_type"
                sig = sigs[0]
                params = ", ".join(p.name for p in sig.params if p.name not in ("self", "cls"))
                info["signature"] = f"{name.name}({params})"
        except Exception:
            pass

        # Add docstring (first paragraph only to keep it concise)
        try:
            doc = name.docstring()
            if doc:
                # Jedi's docstring often starts with the signature line
                # Skip it if it looks like a signature (contains parentheses)
                lines = doc.split("\n")
                # If first line looks like a signature, skip it
                if lines and "(" in lines[0] and ")" in lines[0]:
                    doc = "\n".join(lines[1:]).strip()

                # Take first paragraph (up to first blank line)
                first_para = doc.split("\n\n")[0].strip()
                if first_para:  # Only add if we have actual content
                    info["docstring"] = first_para
        except Exception:
            pass

        results.append(info)

    maybe_json(results, json_out)

# --------------------------------------------------------------------------------------
# Commands: Retrieval/Refactor (Rope)
# --------------------------------------------------------------------------------------

@app.command()
def occurrences(
        file: str = typer.Argument(..., help="Path to the Python file."),
        line: int = typer.Argument(..., help="1-based line number."),
        col: int = typer.Argument(..., help="1-based column number."),
        root: str = typer.Option(".", help="Project root."),
        json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON."),
):
    """
    Semantic occurrences for the symbol at (line, col) using Rope's rename scope analysis.
    Often a more conservative set suitable as a base for safe rename operations.
    """
    ensure("rope" not in _missing, "Rope not installed. Run: pip install rope")
    eng = RopeEngine(pathlib.Path(root))
    maybe_json(eng.occurrences(file, line, col), json_out)

@app.command()
def rename(
        file: str = typer.Argument(..., help="Path to the Python file."),
        line: int = typer.Argument(..., help="1-based line number."),
        col: int = typer.Argument(..., help="1-based column number."),
        new_name: str = typer.Argument(..., help="New identifier name."),
        root: str = typer.Option(".", help="Project root."),
        json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON patches (instead of diffs)."),
        force: bool = typer.Option(False, "--force", help="Apply changes without interactive confirmation."),
):
    """
    Perform a semantic rename with Rope. Produces in-memory patches, shows diffs (or JSON),
    and applies atomically if confirmed or --force is set.
    """
    ensure("rope" not in _missing, "Rope not installed. Run: pip install rope")
    eng = RopeEngine(pathlib.Path(root))
    patches = eng.rename(file, line, col, new_name)
    show_and_apply_patches(pathlib.Path(root), patches, force, json_out)

@app.command("extract-method")
def extract_method(
        file: str = typer.Argument(..., help="Path to the Python file."),
        start_line: int = typer.Argument(..., help="Start line (1-based)."),
        end_line: int = typer.Argument(..., help="End line (1-based, inclusive)."),
        new_name: str = typer.Argument(..., help="Name for the new method."),
        root: str = typer.Option(".", help="Project root."),
        json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON patches (instead of diffs)."),
        force: bool = typer.Option(False, "--force", help="Apply changes without confirmation."),
):
    """
    Extract a contiguous block of code into a new method using Rope.
    Returns preview patches; can apply on confirmation or --force.
    """
    ensure("rope" not in _missing, "Rope not installed. Run: pip install rope")
    eng = RopeEngine(pathlib.Path(root))
    patches = eng.extract_method(file, start_line, end_line, new_name)
    show_and_apply_patches(pathlib.Path(root), patches, force, json_out)

@app.command("extract-var")
def extract_var(
        file: str = typer.Argument(..., help="Path to the Python file."),
        start_line: int = typer.Argument(..., help="Start line (1-based)."),
        end_line: int = typer.Argument(..., help="End line (1-based, inclusive)."),
        new_name: str = typer.Argument(..., help="Name for the new variable."),
        root: str = typer.Option(".", help="Project root."),
        start_col: int = typer.Option(None, "--start-col", help="Optional starting column (1-based). If omitted, starts from beginning of line."),
        end_col: int = typer.Option(None, "--end-col", help="Optional ending column (1-based). If omitted, goes to end of line."),
        json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON patches (instead of diffs)."),
        force: bool = typer.Option(False, "--force", help="Apply changes without confirmation."),
):
    """
    Extract a code expression into a new variable using Rope.
    Returns preview patches; can apply on confirmation or --force.

    By default, extracts entire line(s). Use --start-col and --end-col for precise selection:
    - Neither: extracts entire line(s)
    - Only --start-col: from start_col to end of end_line
    - Only --end-col: from beginning of start_line to end_col
    - Both: precise selection from start_line:start_col to end_line:end_col
    """
    ensure("rope" not in _missing, "Rope not installed. Run: pip install rope")
    eng = RopeEngine(pathlib.Path(root))
    patches = eng.extract_variable(file, start_line, end_line, new_name, start_col, end_col)
    show_and_apply_patches(pathlib.Path(root), patches, force, json_out)

@app.command("move")
def move_symbol_or_module(
        source: str = typer.Argument(..., help="Format: file.py::SymbolName OR just file.py to move the whole module."),
        target_file: str = typer.Argument(..., help="Destination file path (e.g., pkg/newmod.py)."),
        root: str = typer.Option(".", help="Project root."),
        json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON patches (instead of diffs)."),
        force: bool = typer.Option(False, "--force", help="Apply changes without confirmation."),
):
    """
    Move a top-level symbol (function/class) or an entire module to a new file using Rope.
    After moving, you may optionally run `organize-imports` to normalize imports.
    """
    ensure("rope" not in _missing, "Rope not installed. Run: pip install rope")
    eng = RopeEngine(pathlib.Path(root))
    patches = eng.move(source, target_file)
    show_and_apply_patches(pathlib.Path(root), patches, force, json_out)

@app.command("organize-imports")
def organize_imports(
        path: str = typer.Argument(..., help="File or directory path."),
        root: str = typer.Option(".", help="Project root."),
        convert_froms: bool = typer.Option(False, "--froms-to-imports", help="Attempt converting 'from X import Y' to 'import X' + qualified uses."),
        json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON patches (instead of diffs)."),
        force: bool = typer.Option(False, "--force", help="Apply changes without confirmation."),
):
    """
    Normalize imports across a file or directory using Rope's ImportOrganizer.
    Often helpful after move/rename refactors to stabilize import structure.
    """
    ensure("rope" not in _missing, "Rope not installed. Run: pip install rope")
    rootp = pathlib.Path(root)
    eng = RopeEngine(rootp)
    patches = eng.organize_imports((rootp / path), convert_froms)
    show_and_apply_patches(rootp, patches, force, json_out)

# --------------------------------------------------------------------------------------
# Commands: Fast symbol listing
# --------------------------------------------------------------------------------------

@app.command("list")
def list_globals(
        path: str = typer.Argument(..., help="Python file or directory."),
        root: str = typer.Option(".", help="Project root."),
        json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON."),
):
    """
    List top-level classes and functions for a file or recursively for a directory.
    This is a stable, dependency-free summary that agents can use for quick navigation.
    """
    rootp = pathlib.Path(root)
    p = (rootp / path)
    files = [p] if p.is_file() else list(p.rglob("*.py"))
    out: List[Dict[str, Any]] = []
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                out.append({"path": rel_to(rootp, f), "kind": "class", "name": node.name, "line": node.lineno})
            elif isinstance(node, ast.FunctionDef):
                out.append({"path": rel_to(rootp, f), "kind": "function", "name": node.name, "line": node.lineno})
    maybe_json(out, json_out)

# --------------------------------------------------------------------------------------
# Commands: ast-grep codemod (optional)
# --------------------------------------------------------------------------------------

@app.command("codemod")
def codemod(
        rule: str = typer.Argument(..., help="ast-grep rule file (YAML)."),
        root: str = typer.Option(".", help="Project root."),
        apply: bool = typer.Option(False, "--apply", help="Apply rewrites (otherwise dry-run)."),
        json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON."),
):
    """
    Run an AST-based codemod using ast-grep (if installed). Use for large-scale,
    deterministic transformations that don't require full semantic resolution.
    """
    ensure(shutil.which("ast-grep") is not None, "ast-grep not found in PATH")
    rootp = pathlib.Path(root)
    cmd = ["ast-grep", "-c", rule, str(rootp)]
    if apply:
        cmd.append("--rewrite")
    out = subprocess.run(cmd, capture_output=True, text=True)
    # ast-grep returns code 0 with matches, 2 with no matches; treat both as success.
    if out.returncode not in (0, 2):
        eprint(out.stderr.strip())
    maybe_json({"stdout": out.stdout}, json_out)

# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------

def main() -> None:
    """
    Entrypoint. Exposes Typer app. Keep this trivial so agents can import the module
    without triggering side effects.
    """
    app()

if __name__ == "__main__":
    main()
