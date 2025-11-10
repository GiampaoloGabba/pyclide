# PyCLIDE Command Reference

Complete syntax reference for all PyCLIDE commands. See `SKILL.md` for quickstart and usage patterns.

## Global Conventions

**All commands:**
- Output JSON to stdout (always, no flags to change this)
- Support `--root <path>` flag for project root (default: `.`)
- Client auto-starts server via uvx on first request
- Refactoring commands return patches (client NEVER writes to disk - your job to apply)

**Exit codes:**
- `0`: Success
- `1`: Error (missing dependency, server failure, invalid arguments, etc.)

**Base command:** All examples use `python pyclide_client.py`

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

**Returns:** `{"locations": [{"file": "...", "line": N, "column": N}]}`

---

### `refs <file> <line> <col>`

Find all references (usages) of a symbol. Jedi-based broad search.

**Syntax:** `python pyclide_client.py refs <file> <line> <col> [--root <path>]`

**Example:** `python pyclide_client.py refs models/user.py 15 7 --root .`

**Returns:** `{"locations": [{"file": "...", "line": N, "column": N}, ...]}`

**Note:** For rename-safe references, use `occurrences` (Rope-based).

---

### `hover <file> <line> <col>`

Get symbol information: type, signature, docstring.

**Syntax:** `python pyclide_client.py hover <file> <line> <col> [--root <path>]`

**Example:** `python pyclide_client.py hover app.py 42 10 --root .`

**Returns:** `{"signature": "func_name(arg1, arg2)", "docstring": "...", "type": "function"}`

---

## Refactoring Commands (Rope)

### `occurrences <file> <line> <col>`

Find semantic occurrences within rename scope. More conservative than `refs`, safe for preview before renaming.

**Syntax:** `python pyclide_client.py occurrences <file> <line> <col> [--root <path>]`

**Example:** `python pyclide_client.py occurrences app.py 30 8 --root .`

**Returns:** `{"locations": [{"file": "app.py", "line": 30, "column": 8}, ...]}`

---

### `rename <file> <line> <col> <new-name>`

Semantic rename: renames symbol definition, all references, and updates imports automatically.

**Syntax:** `python pyclide_client.py rename <file> <line> <col> <new-name> [--root <path>]`

**Arguments:**
- `new-name`: New identifier (must be valid Python identifier)

**Example:** `python pyclide_client.py rename utils.py 20 5 new_func --root .`

**Returns:** `{"patches": {"utils.py": "new file content...", "app.py": "updated imports..."}}`

**Important:** Client returns patches as JSON. YOU must apply them to disk (Write tool).

---

### `extract-method <file> <start-line> <end-line> <new-method-name>`

Extract code block (lines `start-line` to `end-line`) into a new method.

**Syntax:** `python pyclide_client.py extract-method <file> <start-line> <end-line> <new-method-name> [--root <path>]`

**Arguments:**
- `start-line`, `end-line`: Inclusive range (1-based)
- `new-method-name`: Name for extracted method

**Example:** `python pyclide_client.py extract-method app.py 50 60 validate_input --root .`

**Returns:** `{"patches": {"app.py": "...new file with extracted method..."}}`

---

### `extract-var <file> <start-line> <end-line> <new-var-name> [--start-col <N>] [--end-col <N>]`

Extract expression into a new variable. Supports precise column selection.

**Syntax:** `python pyclide_client.py extract-var <file> <start-line> <end-line> <new-var-name> [--start-col <N>] [--end-col <N>] [--root <path>]`

**Column behavior:**
- No columns: Extract entire line(s)
- `--start-col` only: From column to end of line
- `--end-col` only: From start of line to column
- Both: Precise range selection

**Example (full line):** `python pyclide_client.py extract-var app.py 42 42 user_name --root .`

**Example (precise range):** `python pyclide_client.py extract-var app.py 20 20 sum_val --start-col 16 --end-col 21 --root .`

**Returns:** `{"patches": {"app.py": "..."}}`

---

### `move <file> <line> <col> <target-file>`

Move symbol at position to target file. Updates imports automatically.

**Syntax:** `python pyclide_client.py move <file> <line> <col> <target-file> [--root <path>]`

**Arguments:**
- `file`, `line`, `col`: Position of symbol to move
- `target-file`: Destination file path (relative to `--root`)

**Example:** `python pyclide_client.py move utils.py 10 5 billing/helpers.py --root .`

**Returns:** `{"patches": {"utils.py": "...", "billing/helpers.py": "...", "app.py": "updated imports..."}}`

**Note:** Rope moves the symbol and updates imports. Always run `organize-imports` after.

---

### `organize-imports <path>`

Normalize imports in file or directory (recursive).

**Syntax:** `python pyclide_client.py organize-imports <path> [--root <path>]`

**Arguments:**
- `path`: File or directory to organize (relative to `--root`)

**Example (file):** `python pyclide_client.py organize-imports app.py --root .`

**Example (directory):** `python pyclide_client.py organize-imports src --root .`

**Returns:** `{"patches": {"app.py": "...", "src/models.py": "...", ...}}`

**Behavior:**
- Sorts imports (stdlib → third-party → local)
- Removes duplicates
- Groups related imports
- Removes unused imports

---

## Utility Commands (Local - No Server)

### `list <path>`

List top-level classes and functions in file or directory. AST-based, very fast, runs locally (no server).

**Syntax:** `python pyclide_client.py list <path> [--root <path>]`

**Arguments:**
- `path`: File or directory to list (recursive for directories)

**Example (file):** `python pyclide_client.py list app.py --root .`

**Example (directory):** `python pyclide_client.py list src --root .`

**Returns:** `[{"path": "app.py", "kind": "class|function", "name": "MyClass", "line": 10}, ...]`

**Note:** Only lists top-level symbols (not nested classes/methods).

---

### `codemod <rule-file.yml> [--apply]`

AST-based code transformations using ast-grep. Runs locally (no server).

**Syntax:** `python pyclide_client.py codemod <rule-file.yml> [--apply] [--root <path>]`

**Arguments:**
- `rule-file.yml`: ast-grep YAML rule file
- `--apply`: Apply transformations (default: dry-run preview)

**Example (preview):** `python pyclide_client.py codemod rules/fix-logging.yml --root .`

**Example (apply):** `python pyclide_client.py codemod rules/fix-logging.yml --apply --root .`

**Returns:** `{"stdout": "...", "stderr": "...", "returncode": N, "applied": true|false}`

**Requirements:** `ast-grep` must be installed separately (`npm install -g @ast-grep/cli`)

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
{
  "locations": [
    {"file": "relative/path.py", "line": 42, "column": 5}
  ]
}
```

### Hover information
```json
{
  "signature": "function_name(arg1, arg2, kwarg=default)",
  "docstring": "First paragraph of docstring",
  "type": "function"
}
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
  "stdout": "ast-grep output (matches, changes, statistics)",
  "stderr": "",
  "returncode": 0,
  "applied": false
}
```

---

## Server Architecture

**Client-Server Model:**
1. Client (`pyclide_client.py`) sends HTTP requests to server
2. Server auto-starts via `uvx` on first request (per workspace)
3. Server caches Jedi scripts + Rope project state
4. Server auto-shuts down after 30min inactivity
5. Server registry: `~/.pyclide/servers.json` (auto-managed)

**Performance:**
- First request: ~2-3s (server startup + cache building)
- Subsequent requests: <100ms (cached)
- FileWatcher auto-invalidates cache on file modifications

**Requirements:**
- Python 3.8+
- `uvx` (install via `pip install uv`)

---

## Common Workflows

**Rename Safely:**
```bash
# 1. Preview what will be renamed
python pyclide_client.py occurrences file.py 20 5 --root .

# 2. Get rename patches
python pyclide_client.py rename file.py 20 5 new_name --root .

# 3. Apply patches (your job - use Write tool)
```

**Extract and Clean:**
```bash
# 1. Extract method
python pyclide_client.py extract-method app.py 50 75 validate --root .

# 2. Organize imports
python pyclide_client.py organize-imports . --root .

# 3. Apply all patches
```

**Move Symbol:**
```bash
# 1. Move to new file
python pyclide_client.py move utils.py 15 8 lib/helpers.py --root .

# 2. Organize imports
python pyclide_client.py organize-imports . --root .

# 3. Apply patches
```

---

## Troubleshooting

**Server won't start:**
- Ensure `uvx` is installed: `pip install uv`
- Check server logs in registry: `cat ~/.pyclide/servers.json`

**Stale cache:**
- FileWatcher auto-invalidates on file changes
- Manual invalidation: wait 30min for auto-shutdown, or kill server process

**Import errors after refactoring:**
- Always run `organize-imports` after `move` or manual edits
- Rope may miss some dynamic imports - verify patches before applying
