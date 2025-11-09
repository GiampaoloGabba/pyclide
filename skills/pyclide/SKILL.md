---
name: pyclide
description: >
  Python semantic IDE using Jedi+Rope: go-to-definition, find-references, rename with automatic import updates,
  extract method/variable, move symbols between files, organize imports, and get hover info (signatures/docstrings).

  Triggers: "python definition", "python references", "python rename", "python refactor",
  "extract python method", "extract python variable", "move python function", "move python class",
  "organize python imports", "python semantic search", "python hover info", "python symbol info",
  "refactor python code", "python code navigation"
---

# PyCLIDE - Python Semantic IDE

Semantic code navigation and refactoring for Python using Jedi (navigation) + Rope (refactoring).

**Standalone binary** - no pip dependencies required. All commands output JSON by default.

## When to Use

✅ **Use PyCLIDE for:**
- Navigate: jump to definitions, find references, get symbol info
- Refactor: rename with import updates, extract methods/variables
- Reorganize: move symbols between files, organize imports

❌ **DO NOT use for:**
- Text search → use Claude Code's native Grep tool
- Non-Python files

## Command Syntax

All commands use: `pyclide-wrapper.sh <command> <args> [--root .] [--force]`

### Navigation Commands (Jedi)

**`defs <file> <line> <col>`**
- Jump to symbol definition
- Example: `pyclide-wrapper.sh defs app.py 10 5 --root .`
- Returns: `[{"path": "...", "line": N, "column": N, "name": "...", "type": "class|function|..."}]`

**`refs <file> <line> <col>`**
- Find all symbol references (broad search)
- Returns: List of usage locations

**`hover <file> <line> <col>`**
- Get symbol info: type, signature, docstring
- Returns: `[{"name": "...", "type": "...", "signature": "...", "docstring": "..."}]`

### Refactoring Commands (Rope)

**`occurrences <file> <line> <col>`**
- Find semantic occurrences (rename scope preview)
- More conservative than `refs`, safe for renaming
- Returns: List of locations that will be renamed

**`rename <file> <line> <col> <new-name> [--force]`**
- Semantic rename with automatic import updates
- Preview mode (default): shows diff, prompts confirmation
- `--force`: apply immediately without confirmation
- Updates: symbol definition, references, imports

**`extract-method <file> <start-line> <end-line> <method-name> [--force]`**
- Extract code block into new method
- Automatically handles parameters and return values
- Example: `pyclide-wrapper.sh extract-method app.py 50 60 validate_input --root . --force`

**`extract-var <file> <start-line> <end-line> <var-name> [--start-col N] [--end-col N] [--force]`**
- Extract expression into new variable
- Column flags for precise selection:
  - No columns: extract entire line(s)
  - `--start-col` only: from column to end of line
  - `--end-col` only: from start of line to column
  - Both: precise range selection

**`move <source-spec> <target-file> [--force]`**
- Move symbol or module, update imports
- Symbol: `utils.py::ClassName` or `utils.py::function_name`
- Module: `old/path.py` → moves entire file
- Example: `pyclide-wrapper.sh move utils.py::Helper billing/helpers.py --root . --force`

**`organize-imports <path> [--froms-to-imports] [--force]`**
- Normalize imports in file or directory
- Sorts, groups (stdlib/third-party/local), removes duplicates
- `--froms-to-imports`: convert `from X import Y` to `import X`
- Example: `pyclide-wrapper.sh organize-imports src --root . --force`

### Utility Commands

**`list <path>`**
- List top-level classes/functions (AST-based, very fast)
- Path: file or directory
- Returns: `[{"path": "...", "kind": "class|function", "name": "...", "line": N}]`

**`codemod <rule-file.yml> [--apply]`**
- AST-based transformations using ast-grep
- Requires `ast-grep` installed separately
- Default: dry-run preview
- `--apply`: apply transformations

## Essential Flags

- `--root <path>`: Project root for cross-file analysis (default: `.`)
- `--force`: Skip confirmation prompts (mutating commands)
- `--json` / `--no-json`: Output format (default: `--json`)

## Common Agent Patterns

**Safe Rename Workflow:**
```bash
# 1. Preview scope
pyclide-wrapper.sh occurrences file.py 20 5 --root .

# 2. Execute rename
pyclide-wrapper.sh rename file.py 20 5 new_name --root . --force
```

**Refactoring Workflow:**
```bash
# 1. Understand symbol
pyclide-wrapper.sh hover app.py 42 10 --root .

# 2. Extract method
pyclide-wrapper.sh extract-method app.py 50 75 validate_input --root . --force

# 3. Clean up
pyclide-wrapper.sh organize-imports . --root . --force
```

**Code Reorganization:**
```bash
# 1. Move symbol
pyclide-wrapper.sh move utils.py::helper_func lib/helpers.py --root . --force

# 2. Organize imports
pyclide-wrapper.sh organize-imports . --root . --force
```

## Key Details

- **Output**: All commands return JSON arrays/objects by default
- **Errors**: Exit code 2 on validation errors (missing deps, file not found)
- **Patches**: Mutating commands show diffs (or JSON patches with `--json`)
- **Platform**: Wrapper auto-selects binary (Windows: `.exe`, Linux: `-linux`, macOS: `-macos`)

## See Also

- **Complete reference**: `skills/pyclide/REFERENCE.md` - detailed syntax, examples, troubleshooting
