---
name: pyclide
description: >
  Semantic code analysis and refactoring for Python projects using Jedi and Rope.
  Provides go-to-definition, find-references, rename with import updates, extract method/variable,
  move symbols between files, organize imports, and hover info.
  Use when navigating Python code, performing semantic search, renaming symbols, refactoring code,
  extracting methods or variables, moving functions or classes, organizing imports, or getting
  symbol information in Python projects.
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

## Output Formats & Applying Changes

**All refactoring commands** (`rename`, `extract-method`, `extract-var`, `move`, `organize-imports`) **support two output formats:**

**`--output-format diff` (default)** - Unified diffs (90% token savings)
- Returns only changed lines with context
- Apply using Edit tool (extract old_string → new_string from diff)
- Most efficient for incremental changes

**`--output-format full`** - Complete file contents
- Returns entire new file contents
- Apply using Write tool
- Use as fallback if diff parsing fails

**Example response (diff format):**
```json
{
  "patches": {
    "file.py": "--- a/file.py\n+++ b/file.py\n@@ -20,1 +20,1 @@\n-old_name\n+new_name\n"
  },
  "format": "diff"
}
```

**Your job:** Parse the diff to extract old_string/new_string, then use Edit tool to apply changes.

## Flags and Output

**Global flags:**
- `--root <path>`: Project root (default: `.`)
- `--output-format <diff|full>`: Refactoring output (default: `diff`) - see "Output Formats" above

**extract-var only:**
- `--start-col <N>`, `--end-col <N>`: Precise column selection

**Output:**
- All commands output JSON to stdout
- Refactoring: `{"patches": {...}, "format": "diff|full"}` - see "Output Formats" section
- Navigation: `{"locations": [...]}` or hover info

## Common Agent Patterns

**Safe Rename Workflow:**
```bash
# 1. Preview scope
python pyclide_client.py occurrences file.py 20 5 --root .

# 2. Get patches (returns diff by default)
python pyclide_client.py rename file.py 20 5 new_name --root .

# 3. Apply patches using Edit tool (parse diff for old/new strings)
```

**Refactoring Workflow:**
```bash
# 1. Understand symbol
python pyclide_client.py hover app.py 42 10 --root .

# 2. Extract method
python pyclide_client.py extract-method app.py 50 75 validate_input --root .

# 3. Clean up imports
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
- **Output**: All commands output JSON to stdout (always, no flags to change this)
- **Patches**: Refactoring commands return `{"patches": {path: content}}` - client NEVER writes to disk
- **Your job**: Parse JSON, apply patches yourself (Write tool)
- **Registry**: Servers tracked in `~/.pyclide/servers.json`, auto-managed
- **Requirements**: Python 3.8+, uvx (auto-installed via `pip install uv`)

## Performance Tips

- First request per workspace: ~2-3s (server startup + cache building)
- Subsequent requests: <100ms (cached)
- Server persists across multiple requests (reuse cache)
- FileWatcher auto-invalidates cache on file changes

## See Also

- **Complete reference**: `skills/pyclide/REFERENCE.md` - detailed syntax, examples, troubleshooting
