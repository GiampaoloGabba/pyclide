# PyCLIDE Command Reference

Complete syntax reference for all PyCLIDE commands. See `SKILL.md` for quickstart and usage patterns.

## Global Conventions

**All commands support:**
- `--root <path>`: Project root directory (default: `.`)
- `--json` / `--no-json`: Output format (default: `--json`)
- Mutating commands (rename, extract-*, move, organize-imports) support `--force` to skip confirmation

**Exit codes:**
- `0`: Success
- `2`: Error (missing dependency, file not found, invalid arguments, etc.)

**Base command:** All examples use `python pyclide_client.py` which auto-selects platform binary.

---

## Navigation Commands (Jedi)

### `defs <file> <line> <col>`

Jump to where a symbol is defined.

**Syntax:** `python pyclide_client.py defs <file> <line> <col> [--root <path>]`

**Arguments:**
- `file`: Path to Python file (relative to `--root` or absolute)
- `line`: 1-based line number
- `col`: 1-based column number

**Example:** `python pyclide_client.py defs app/models.py 10 15 --root /path/to/project`

**Returns:** `[{"path": "...", "line": N, "column": N, "name": "SymbolName", "type": "class|function|module|..."}]`

---

### `refs <file> <line> <col>`

Find all references (usages) of a symbol. Jedi-based broad search.

**Syntax:** `python pyclide_client.py refs <file> <line> <col> [--root <path>]`

**Example:** `python pyclide_client.py refs models/user.py 15 7 --root .`

**Returns:** List of locations (same structure as `defs`)

**Note:** For rename-safe references, use `occurrences` (Rope-based).

---

### `hover <file> <line> <col>`

Get symbol information: type, signature, docstring.

**Syntax:** `python pyclide_client.py hover <file> <line> <col> [--root <path>]`

**Example:** `python pyclide_client.py hover app.py 42 10 --root .`

**Returns:** `[{"name": "func_name", "type": "function", "full_name": "module.func_name", "signature": "func_name(arg1, arg2)", "docstring": "First paragraph of docstring..."}]`

---

## Refactoring Commands (Rope)

### `occurrences <file> <line> <col>`

Find semantic occurrences within rename scope. More conservative than `refs`, safe for preview before renaming.

**Syntax:** `python pyclide_client.py occurrences <file> <line> <col> [--root <path>]`

**Example:** `python pyclide_client.py occurrences app.py 30 8 --root .`

**Returns:** `[{"path": "app.py", "line": 30, "column": 8}, {"path": "app.py", "line": 35, "column": 15}, ...]`

---

### `rename <file> <line> <col> <new-name> [--force]`

Semantic rename: renames symbol definition, all references, and updates imports automatically.

**Syntax:** `python pyclide_client.py rename <file> <line> <col> <new-name> [--root <path>] [--force]`

**Arguments:**
- `new-name`: New identifier (must be valid Python identifier)

**Behavior:**
- Without `--force`: Shows unified diff of all changes, prompts for confirmation
- With `--force`: Applies changes immediately

**Example (preview):** `python pyclide_client.py rename utils.py 20 5 new_func --root .`

**Example (force):** `python pyclide_client.py rename utils.py 20 5 new_func --root . --force`

**Returns (--json):** `{"patches": {"utils.py": "new file content...", "app.py": "updated imports..."}}`

**Returns (--no-json):** Unified diff output

---

### `extract-method <file> <start-line> <end-line> <new-method-name> [--force]`

Extract a code block into a new method. Rope automatically identifies parameters, return values, and placement.

**Syntax:** `python pyclide_client.py extract-method <file> <start-line> <end-line> <new-method-name> [--root <path>] [--force]`

**Arguments:**
- `start-line`: First line of block (1-based, inclusive)
- `end-line`: Last line of block (1-based, inclusive)
- `new-method-name`: Name for the extracted method

**Example:** `python pyclide_client.py extract-method app.py 50 60 validate_input --root . --force`

**Returns:** `{"patches": {"app.py": "code with new method + call site"}}`

---

### `extract-var <file> <start-line> <end-line> <new-var-name> [--start-col <N>] [--end-col <N>] [--force]`

Extract an expression into a new variable. Supports precise column-based selection.

**Syntax:** `python pyclide_client.py extract-var <file> <start-line> <end-line> <new-var-name> [--start-col <N>] [--end-col <N>] [--root <path>] [--force]`

**Column selection behavior:**
- **No `--start-col` or `--end-col`**: Extracts entire line(s)
- **Only `--start-col`**: Extracts from `start-col` to end of `end-line`
- **Only `--end-col`**: Extracts from beginning of `start-line` to `end-col`
- **Both specified**: Extracts precise range from `start-line:start-col` to `end-line:end-col`

**Example (full line):** `python pyclide_client.py extract-var app.py 42 42 user_name --root . --force`

**Example (precise range):** `python pyclide_client.py extract-var app.py 20 20 sum_val --start-col 16 --end-col 21 --root . --force`

**Returns:** `{"patches": {"app.py": "code with variable extraction"}}`

---

### `move <source-spec> <target-file> [--force]`

Move a symbol or entire module to another file, updating all imports automatically.

**Syntax (move symbol):** `python pyclide_client.py move <file>::<SymbolName> <target-file> [--root <path>] [--force]`

**Syntax (move module):** `python pyclide_client.py move <source-file> <target-file> [--root <path>] [--force]`

**Source spec formats:**
- `utils.py::ClassName` - Move top-level class
- `utils.py::function_name` - Move top-level function
- `old/module.py` - Move entire module (no `::` separator)

**Example (move symbol):** `python pyclide_client.py move utils.py::calculate_tax billing/taxes.py --root . --force`

**Example (move module):** `python pyclide_client.py move old/path.py new/location.py --root . --force`

**Returns:** `{"patches": {"utils.py": "source with symbol removed", "billing/taxes.py": "target with symbol added", "app.py": "updated imports"}}`

**Recommendation:** Run `organize-imports` after moving symbols to clean up imports.

---

### `organize-imports <path> [--froms-to-imports] [--force]`

Normalize imports in a file or directory: sorts, groups (stdlib/third-party/local), removes duplicates.

**Syntax:** `python pyclide_client.py organize-imports <path> [--root <path>] [--froms-to-imports] [--force]`

**Arguments:**
- `path`: File or directory path (if directory, processes all `.py` files recursively)

**Options:**
- `--froms-to-imports`: Convert `from X import Y` to `import X` with qualified usage (e.g., `from os import path` → `import os` + `os.path`)

**Example (single file):** `python pyclide_client.py organize-imports app.py --root . --force`

**Example (directory):** `python pyclide_client.py organize-imports src --root . --force`

**Example (convert froms):** `python pyclide_client.py organize-imports app.py --froms-to-imports --root . --force`

**Returns:** `{"patches": {"app.py": "organized imports", "utils.py": "organized imports"}}`

**Grouping order:** stdlib imports → third-party imports → local imports (with blank lines between groups)

---

## Utility Commands

### `list <path>`

List all top-level classes and functions in a file or directory. Uses AST parsing (very fast, zero dependencies).

**Syntax:** `python pyclide_client.py list <path> [--root <path>]`

**Arguments:**
- `path`: Python file or directory (recursive if directory)

**Example (file):** `python pyclide_client.py list app.py --root .`

**Example (directory):** `python pyclide_client.py list src --root .`

**Returns:** `[{"path": "app.py", "kind": "class", "name": "Application", "line": 10}, {"path": "app.py", "kind": "function", "name": "main", "line": 45}]`

**Note:** Only finds top-level definitions (not nested classes/functions).

---

### `codemod <rule-file.yml> [--apply]`

Run AST-based code transformations using ast-grep rules.

**Syntax:** `python pyclide_client.py codemod <rule-file.yml> [--root <path>] [--apply]`

**Arguments:**
- `rule-file.yml`: Path to ast-grep rule file (YAML format)

**Options:**
- `--apply`: Apply transformations (default: dry-run preview only)

**Requirements:** `ast-grep` must be installed (`cargo install ast-grep` or download from https://github.com/ast-grep/ast-grep/releases)

**Example (preview):** `python pyclide_client.py codemod rules/update-api.yml --root .`

**Example (apply):** `python pyclide_client.py codemod rules/update-api.yml --root . --apply`

**Returns:** `{"stdout": "ast-grep output with matched locations and changes"}`

**ast-grep rule example:**
```yaml
id: update-api-call
language: python
rule:
  pattern: old_api_call($ARGS)
fix: new_api_call($ARGS)
```

**Use cases:** Large-scale API migrations, pattern-based refactoring, codebase-wide updates.

---

## JSON Output Format Reference

### Location objects (defs, refs, occurrences)
```json
[
  {"path": "relative/path.py", "line": 42, "column": 5, "name": "symbol_name", "type": "class|function|module"}
]
```

### Hover information
```json
[
  {
    "name": "function_name",
    "type": "function",
    "full_name": "module.submodule.function_name",
    "signature": "function_name(arg1, arg2, kwarg=default)",
    "docstring": "First paragraph of docstring (up to first blank line)"
  }
]
```

### Patches (rename, extract-*, move, organize-imports)
```json
{
  "patches": {
    "file1.py": "complete new file contents...",
    "file2.py": "complete new file contents..."
  }
}
```

### Symbol list
```json
[
  {"path": "app.py", "kind": "class", "name": "Application", "line": 10},
  {"path": "app.py", "kind": "function", "name": "main", "line": 45}
]
```

### Codemod output
```json
{
  "stdout": "ast-grep output (matches, changes, statistics)"
}
```

---

## Common Workflows

### Safe Rename
```bash
# 1. Preview what will be renamed
python pyclide_client.py occurrences file.py 20 5 --root .

# 2. Execute rename
python pyclide_client.py rename file.py 20 5 new_name --root . --force

# 3. Clean up imports
python pyclide_client.py organize-imports . --root . --force
```

### Extract and Refactor
```bash
# 1. Understand symbol context
python pyclide_client.py hover app.py 42 10 --root .

# 2. Extract method
python pyclide_client.py extract-method app.py 50 75 validate_input --root . --force

# 3. Organize imports
python pyclide_client.py organize-imports app.py --root . --force
```

### Code Reorganization
```bash
# 1. Move symbol to new location
python pyclide_client.py move utils.py::helper_func lib/helpers.py --root . --force

# 2. Organize all imports
python pyclide_client.py organize-imports . --root . --force
```

---

## Troubleshooting

**"Not a resolvable python identifier"**
- Position must point to identifier name, not docstrings/whitespace
- Rope uses 1-based lines and columns

**Cross-file references incomplete**
- Works best with standard packages (`__init__.py`, relative imports)
- May miss complex imports (`sys.path.insert()`)

**Tip:** Use `--json` (without `--force`) to preview changes before applying
