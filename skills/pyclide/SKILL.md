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

**Client-server architecture** - Client auto-starts server via uvx, server caches Jedi/Rope state for fast responses.

## When to Use

✅ **Use PyCLIDE for:**
- Navigate: jump to definitions, find references, get symbol info
- Refactor: rename with import updates, extract methods/variables
- Reorganize: move symbols between files, organize imports

❌ **DO NOT use for:**
- Text search → use Claude Code's native Grep tool
- Non-Python files

## Command Syntax

All commands use: `python pyclide_client.py <command> <args> [--root .]`

**Server auto-starts** on first request (via uvx), persists cache, auto-shuts down after 30min inactivity.

### Navigation Commands (Jedi - Fast)

**`defs <file> <line> <col>`**
- Jump to symbol definition
- Example: `python pyclide_client.py defs app.py 10 5 --root .`
- Returns: `{"locations": [{"file": "...", "line": N, "column": N}]}`

**`refs <file> <line> <col>`**
- Find all symbol references (broad search)
- Returns: List of usage locations

**`hover <file> <line> <col>`**
- Get symbol info: type, signature, docstring
- Returns: `{"signature": "...", "docstring": "...", "type": "..."}`

### Refactoring Commands (Rope - Semantic)

**`occurrences <file> <line> <col>`**
- Find semantic occurrences (rename scope preview)
- More conservative than `refs`, safe for renaming
- Returns: List of locations that will be renamed

**`rename <file> <line> <col> <new-name>`**
- Semantic rename with automatic import updates
- Returns patches: `{"patches": {"file.py": "new_content", ...}}`
- Updates: symbol definition, references, imports

**`extract-method <file> <start-line> <end-line> <method-name>`**
- Extract code block into new method
- Automatically handles parameters and return values
- Example: `python pyclide_client.py extract-method app.py 50 60 validate_input --root .`

**`extract-var <file> <start-line> <end-line> <var-name> [--start-col N] [--end-col N]`**
- Extract expression into new variable
- Column flags for precise selection:
  - No columns: extract entire line(s)
  - `--start-col` only: from column to end of line
  - `--end-col` only: from start of line to column
  - Both: precise range selection

**`move <file> <line> <col> <target-file>`**
- Move symbol to target file, update imports
- Example: `python pyclide_client.py move utils.py 10 5 billing/helpers.py --root .`

**`organize-imports <path>`**
- Normalize imports in file or directory
- Sorts, groups (stdlib/third-party/local), removes duplicates
- Example: `python pyclide_client.py organize-imports src --root .`

### Local Commands (No Server)

**`list <path>`**
- List top-level classes/functions (AST-based, very fast, runs locally)
- Path: file or directory
- Returns: `[{"path": "...", "kind": "class|function", "name": "...", "line": N}]`

**`codemod <rule-file.yml> [--apply]`**
- AST-based transformations using ast-grep (runs locally)
- Requires `ast-grep` installed separately
- Default: dry-run preview
- `--apply`: apply transformations

## Essential Flags

- `--root <path>`: Project root for cross-file analysis (default: `.`)
- All commands output JSON by default

## Common Agent Patterns

**Safe Rename Workflow:**
```bash
# 1. Preview scope
python pyclide_client.py occurrences file.py 20 5 --root .

# 2. Execute rename (apply patches to disk yourself)
python pyclide_client.py rename file.py 20 5 new_name --root .
```

**Refactoring Workflow:**
```bash
# 1. Understand symbol
python pyclide_client.py hover app.py 42 10 --root .

# 2. Extract method
python pyclide_client.py extract-method app.py 50 75 validate_input --root .

# 3. Clean up
python pyclide_client.py organize-imports . --root .
```

**Code Reorganization:**
```bash
# 1. Move symbol
python pyclide_client.py move utils.py 15 8 lib/helpers.py --root .

# 2. Organize imports
python pyclide_client.py organize-imports . --root .
```

## Key Details

- **Architecture**: Client → HTTP → Server (auto-started via uvx)
- **Server**: Caches Jedi scripts + Rope project, auto-shutdown after 30min inactivity
- **Output**: All commands return JSON objects/arrays
- **Patches**: Refactoring commands return `{"patches": {path: content}}` - YOU apply to disk
- **Registry**: Servers tracked in `~/.pyclide/servers.json`, auto-cleanup on restart
- **Requirements**: Python 3.8+, uvx (for server auto-start)

## Performance Tips

- First request per workspace: ~2-3s (server startup + cache building)
- Subsequent requests: <100ms (cached)
- Server persists across multiple requests (reuse cache)
- FileWatcher auto-invalidates cache on file changes

## See Also

- **Complete reference**: `skills/pyclide/REFERENCE.md` - detailed syntax, examples, troubleshooting
