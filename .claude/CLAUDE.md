# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**PyCLIDE** (Python Command-Line IDE) is a Claude Code plugin that provides semantic code analysis and refactoring for Python projects. It unifies Jedi (navigation) and Rope (refactoring) behind a single CLI, with standalone executables to avoid polluting project Python environments.

## Core Architecture

### Single-File CLI Design

The entire application is in **`pyclide.py`** (root directory). This single-file architecture:
- Uses **Typer** for CLI framework
- Integrates **Jedi** for navigation (definitions, references, hover info)
- Integrates **Rope** for refactoring (rename, extract, move, organize imports)
- Supports graceful degradation when dependencies are missing
- Returns JSON by default for agent parsing

### Key Components

1. **RopeEngine** (pyclide.py:165-417)
   - Wraps Rope's `Project` for project-aware refactoring
   - All refactoring operations return **in-memory patches** (Dict[str, str] mapping file paths to new contents)
   - Never writes to disk directly; caller decides when to apply
   - Converts between 1-based (line, col) coordinates and Rope's byte offsets

2. **Jedi Integration** (pyclide.py:423-449)
   - Provides lightweight navigation (defs, refs, hover)
   - Less precise than Rope for refactoring but faster for queries
   - Returns normalized location dictionaries

3. **Patch System** (pyclide.py:454-481)
   - `show_and_apply_patches()`: Previews unified diffs or emits JSON
   - `confirm_apply()`: Interactive confirmation unless `--force` is used
   - `write_text_atomic()`: Uses temp files + rename for atomic writes

### Commands Architecture

All commands follow the pattern:
1. **Analyze** using Jedi/Rope
2. **Return** results as JSON or human-readable format
3. **Optionally apply** (for mutating commands) with atomic writes

**Navigation Commands** (Jedi):
- `defs` - Go to definition
- `refs` - Find references
- `hover` - Get type/signature/docstring

**Refactoring Commands** (Rope):
- `occurrences` - Semantic occurrences (rename scope preview)
- `rename` - Semantic rename with import updates
- `extract-method` - Extract code block to method
- `extract-var` - Extract expression to variable (supports precise column ranges)
- `move` - Move symbols/modules between files
- `organize-imports` - Normalize imports

**Utility Commands**:
- `list` - Fast AST-based symbol listing
- `codemod` - AST transformations via ast-grep (optional)

## Development Commands

### Running Tests

```bash
# Run all tests
pytest

# Run specific test categories
pytest -m jedi          # Jedi navigation tests
pytest -m rope          # Rope refactoring tests
pytest -m integration   # Integration tests
pytest -m "not slow"    # Skip slow tests

# Run with coverage (if pytest-cov installed)
pytest --cov=pyclide --cov-report=html
```

### Running from Source

```bash
# Install dependencies first
pip install typer[all] jedi rope

# Run directly from root directory
python pyclide.py --version
python pyclide.py defs app.py 10 5 --root .
python pyclide.py list . --root .
```

### Building Binaries

```bash
# Install build dependencies
pip install pyinstaller typer[all] jedi rope

# Build for your platform
./build/build.sh         # Linux/macOS/Git Bash
build\build.bat          # Windows

# Output: bin/pyclide-{platform} or bin/pyclide.exe
```

**Cross-platform builds**: Run build script on each OS to create all binaries.

## Project Structure

```
python-semantic-ide/
├── pyclide.py                    # 🔥 Main source (entire CLI in one file)
├── .claude-plugin/
│   └── plugin.json               # Plugin manifest
├── skills/pyclide/
│   ├── SKILL.md                  # Concise skill reference for Claude
│   └── REFERENCE.md              # Complete command documentation
├── bin/                          # Standalone executables (gitignored)
├── scripts/
│   ├── pyclide-wrapper.sh        # Auto-detects platform binary
│   └── pyclide-wrapper.bat
├── build/
│   ├── build.sh                  # PyInstaller build script
│   └── build.bat
├── tests/
│   ├── conftest.py               # Pytest configuration
│   ├── test_jedi_features.py     # Jedi navigation tests
│   ├── test_rope_features.py     # Rope refactoring tests
│   ├── test_integration.py       # End-to-end tests
│   └── fixtures/                 # Test data
└── pytest.ini                    # Pytest settings
```

## Key Implementation Details

### Coordinate System

- **External API**: 1-based (line, column) for consistency with editors/LSPs
- **Rope Internal**: 0-based byte offsets
- **Conversion**: `byte_offset()` helper (pyclide.py:125-131)

### Extract Variable Column Behavior

The `extract-var` command has flexible column handling (pyclide.py:273-322):
- No columns: extract entire line(s)
- `--start-col` only: from column to end of line
- `--end-col` only: from beginning to column
- Both: precise range selection

### Rope Project Caching

Rope creates a `.ropeproject` directory for caching. This is gitignored and should not be committed.

### Test Fixtures

Tests use `tests/fixtures/` for sample code:
- `sample_module.py` / `sample_usage.py` - Basic navigation tests
- `multifile_refactor/` - Cross-file refactoring tests
- `invalid_syntax.py` - Error handling tests
- `nested_classes.py` - Complex scope tests

## Making Changes

### Modifying the CLI

1. Edit `pyclide.py` in the **root directory**
2. Test locally: `python pyclide.py <command> <args>`
3. Add tests in `tests/test_*.py`
4. Run test suite: `pytest`
5. Rebuild binaries: `./build/build.sh`
6. Update version in:
   - `pyclide.py` line 34: `VERSION = "x.y.z"`
   - `.claude-plugin/plugin.json` line 3: `"version": "x.y.z"`

### Adding New Commands

1. Add command function with `@app.command()` decorator
2. Follow existing patterns:
   - Use `ensure()` for precondition checks
   - Return JSON with `maybe_json()`
   - For mutations: generate patches, show preview, apply on confirmation
3. Update `skills/pyclide/SKILL.md` with new command
4. Add corresponding tests

### Common Patterns

**Safe Refactor Pattern**:
```python
# 1. Create RopeEngine with project root
eng = RopeEngine(pathlib.Path(root))

# 2. Generate in-memory patches (no disk writes)
patches = eng.rename(file, line, col, new_name)

# 3. Preview and optionally apply
show_and_apply_patches(pathlib.Path(root), patches, force, json_out)
```

**Adding New Jedi Feature**:
```python
@app.command()
def new_command(
    file: str = typer.Argument(...),
    line: int = typer.Argument(...),
    col: int = typer.Argument(...),
    root: str = typer.Option("."),
    json_out: bool = typer.Option(True, "--json/--no-json"),
):
    ensure("jedi" not in _missing, "Jedi not installed. Run: pip install jedi")
    scr = jedi_script(pathlib.Path(root), file)
    res = scr.some_jedi_method(line, col)
    maybe_json(jedi_to_locations(res), json_out)
```

## Deployment

### As Claude Code Skill

Copy to personal skills directory:
```bash
# Linux/macOS
cp -r . ~/.claude/skills/pyclide

# Windows
Copy-Item -Recurse . "$env:USERPROFILE\.claude\skills\pyclide"
```

### Distribution

Binaries are gitignored due to size (~40-60 MB each). Users should either:
1. Build locally using `build.sh` / `build.bat`
2. Download pre-built binaries from releases (if publishing)

## Dependencies

**Required (runtime)**:
- Python 3.8+
- typer[all]
- jedi
- rope

**Required (build)**:
- pyinstaller

**Optional (enhanced features)**:
- ast-grep: AST codemods
- ripgrep: Text search fallback (Note: Claude Code has native Grep tool)
- universal-ctags + readtags: Fast symbol indexing

## Important Notes

- Always use `--root` flag pointing to project root for best accuracy
- Rope can struggle with dynamic imports and metaprogramming - always preview patches
- The `move` command uses simple token matching for symbols; run `organize-imports` after moving
- JSON output mode is default and designed for agent parsing
- Test files use pytest markers: `@pytest.mark.jedi`, `@pytest.mark.rope`, `@pytest.mark.integration`
