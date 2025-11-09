# PyCLIDE

High-performance Python semantic analysis server for Claude Code. Provides IDE-quality code navigation and refactoring using Jedi and Rope with persistent hot cache.

## Why a Claude Code Skill?

PyCLIDE is built as a **Claude Code skill** rather than an MCP server for optimal efficiency:

**Token Window Efficiency**
MCP servers load their context into every Claude conversation, consuming precious token window space. Skills load **only when needed** - Claude scans available skills and activates PyCLIDE only when you're working with Python code.

**On-Demand Loading**
When you ask Claude to "find all references to this function", Claude:
1. Identifies this is a Python analysis task
2. Loads the PyCLIDE skill instructions
3. Executes the skill's client code
4. Returns to normal operation

The skill context is released when not in use, keeping your token window available for your code and conversation.

**Deterministic Operations**
Skills can include executable code for tasks where traditional programming is more reliable than token generation. PyCLIDE leverages this for precise AST analysis and refactoring operations.

Learn more about skills: [Claude Code Skills Announcement](https://www.claude.com/blog/skills)

## Features

**Navigation (Jedi-based)**
- Go to definition - Jump to where symbols are defined
- Find references - Find all usages of a symbol
- Hover information - Get type, signature, and docstrings

**Refactoring (Rope-based)**
- Semantic rename - Rename with automatic import updates
- Extract method/variable - Refactor code into reusable components
- Move symbols - Reorganize code between files
- Organize imports - Clean up and normalize imports
- Semantic occurrences - Find references within rename scope

**Utilities**
- List symbols - Quick overview of classes/functions (AST-based)
- AST codemods - Mass transformations with ast-grep (optional)

**Note:** For text search, use Claude Code's native Grep tool (built-in ripgrep integration).

## Architecture

PyCLIDE uses a **client-server architecture** for fast repeated operations:

```
┌─────────────────┐
│  Claude Code    │
│  invokes skill  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      1. Check registry
│  pyclide_client │──────────────────────┐
│  (stdlib only)  │                      │
└────────┬────────┘                      ▼
         │                    ┌──────────────────┐
         │ 2. Start if needed │ Server Registry  │
         │                    │ ~/.pyclide/      │
         ├───────────────────▶│ servers.json     │
         │                    └──────────────────┘
         │ 3. HTTP request
         ▼
┌─────────────────────────────────────┐
│  pyclide-server (per workspace)     │
│  ┌─────────┬──────────┬───────────┐ │
│  │FastAPI  │Hot Cache │File Watch │ │
│  │Port:auto│Jedi+Rope │Invalidate │ │
│  └─────────┴──────────┴───────────┘ │
└─────────────────────────────────────┘
```

**Components:**

- **Client** (`pyclide_client.py`): Lightweight script (stdlib only, ~400 lines) bundled with the skill
- **Server** (`pyclide-server`): Background process with hot RAM cache, auto-downloaded from GitHub
- **Registry** (`~/.pyclide/servers.json`): Tracks running servers per workspace

**Key Capabilities:**

- One server per workspace (isolated environments)
- Auto-start on first use (transparent to user)
- File watcher maintains cache consistency
- Auto-shutdown after 30 minutes inactivity
- Dynamic port allocation (5000-6000 range)

## Installation

### Prerequisites

**Required:**
- Python 3.8+ (already required for Claude Code)
- `uv` package manager: `pip install uv`
- Git (for server download)

**Optional:**
- `ast-grep` for AST transformations: `cargo install ast-grep`

### Install to Claude Code Skills

Copy the skill to your personal skills directory:

```bash
# Linux/macOS
cp -r skills/pyclide ~/.claude/skills/pyclide

# Windows (PowerShell)
Copy-Item -Recurse skills\pyclide "$env:USERPROFILE\.claude\skills\pyclide"
```

**That's it!** The server will be **auto-downloaded from GitHub** on first use.

### First-Time Setup Flow

When Claude Code first invokes PyCLIDE:

1. **Client executes**: `python ~/.claude/skills/pyclide/pyclide_client.py defs app.py 10 5`
2. **Client detects no server** for workspace
3. **Client runs**: `uvx --from git+https://github.com/GiampaoloGabba/pyclide pyclide-server --root /workspace --port 5001 --daemon`
4. **uvx downloads** server from GitHub (first time only, ~3s)
5. **Server starts** in background
6. **Client sends HTTP request** to server
7. **Result returned** to Claude Code

Subsequent invocations use the running server for instant responses.

## Usage

Once installed, Claude Code will **automatically invoke** the skill when you request Python code analysis or refactoring.

### Example Prompts

- "Find all references to the `calculate_tax` function"
- "Rename `old_name` to `new_name` in utils.py line 42"
- "Extract lines 50-60 in app.py into a new method called `validate_input`"
- "Move the `User` class from models.py to user/models.py"
- "Show me what `process_payment` does at line 100"

### Manual Invocation

You can invoke the client directly for testing:

```bash
# Via skill client
python ~/.claude/skills/pyclide/pyclide_client.py defs app.py 10 5 --root .
python ~/.claude/skills/pyclide/pyclide_client.py rename app.py 10 5 new_name --root .
```

### Server Management

Check running servers:

```bash
cat ~/.pyclide/servers.json
```

Stop all servers:

```bash
# Servers auto-shutdown after 30 minutes of inactivity
# Or send shutdown request:
curl -X POST http://127.0.0.1:PORT/shutdown
```

## Performance

**Response Times:**
- First query: ~800ms (cold start - server initialization)
- Subsequent queries: **20-50ms** (hot cache)
- Find references in 10k LOC project: **100-200ms**

**Why Fast:**
- **Hot RAM cache**: Jedi and Rope analysis results stay in memory
- **File watcher**: Cache invalidation only on file changes
- **Persistent process**: No Python interpreter startup overhead per request

**Memory Footprint:**
~50-120MB per workspace (includes Python runtime, Jedi, Rope, AST caches)

## Development

### Running Server Locally

For development/testing:

```bash
# Install dependencies
pip install -e .

# Start server manually
python -m pyclide_server --root . --port 5555

# In another terminal, test with client
python skills/pyclide/pyclide_client.py defs app.py 10 5 --root .
```

### Running Tests

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run specific test categories
pytest -m unit              # Fast unit tests
pytest -m integration       # Integration tests
pytest -m e2e              # End-to-end tests
pytest -m "not slow"       # Skip slow tests

# With coverage
pytest --cov=pyclide_server --cov-report=html
```

### Making Changes

**Server code** (`pyclide_server/`):
1. Edit server modules
2. Test locally: `python -m pyclide_server --root . --port 5555`
3. Run tests: `pytest tests/`
4. Update version in `pyproject.toml` and `pyclide_server/__init__.py`
5. Push to GitHub (instant deployment)

**Client code** (`skills/pyclide/pyclide_client.py`):
1. Edit client (keep stdlib-only!)
2. Test: `python skills/pyclide/pyclide_client.py defs ...`
3. Update `SKILL.md` if command interface changes

### Deployment

The server is deployed directly from GitHub:

```bash
# Users install via uvx (automatic on first use)
uvx --from git+https://github.com/GiampaoloGabba/pyclide pyclide-server --help

# Or manually for testing
git clone https://github.com/GiampaoloGabba/pyclide
cd pyclide
pip install -e .
python -m pyclide_server --root . --port 5555
```

## Known Limitations

### Server-Specific

**File Watcher**:
- May miss changes to files ignored by .gitignore (by design)
- Debouncing (100ms) may delay cache invalidation slightly

**Auto-Shutdown**:
- Server shuts down after 30 minutes inactivity
- Next query will restart server (~800ms first request)

**Port Allocation**:
- Uses ports 5000-6000
- If all ports in use, client will fail
- Manual cleanup: delete `~/.pyclide/servers.json`

### Rope Refactoring Limitations

**Cross-Directory References**:
- May not find all references with `sys.path.insert()` or complex imports
- Works best with standard Python package structures

**Coordinate Precision**:
- Refactoring requires exact positioning on identifier
- Must point to symbol name, not docstrings/comments
- Uses 1-based line and column positions

**Dynamic Code**:
- String-based imports not tracked (`__import__()`, `importlib`)
- `exec()`, `eval()` references not detected

**Recommendations**:
- Preview changes before applying (server returns JSON patches)
- Run tests after refactoring
- Client (Claude Code) decides when to apply patches

### Jedi Navigation Notes

- Works best with properly structured Python packages
- `goto` may return import locations instead of definitions
- Type inference limited for dynamic code

## Troubleshooting

### "uvx not found"

Install uv package manager:
```bash
pip install uv
```

Or visit: https://docs.astral.sh/uv/

### "git not found"

Install Git from: https://git-scm.com/downloads

### Server Won't Start

Check logs:
```bash
# Server logs errors to stderr
# Client shows server startup errors

# Check if port is in use
netstat -an | grep 5000-6000  # Unix
netstat -an | findstr "5000"  # Windows
```

Manual cleanup:
```bash
# Remove stale registry entries
rm ~/.pyclide/servers.json

# Kill stuck servers
ps aux | grep pyclide-server  # Unix
tasklist | findstr python     # Windows
```

### "No available ports in range 5000-6000"

Too many servers running or port conflicts:
```bash
# Stop all servers
pkill -f pyclide-server  # Unix
taskkill /F /IM python.exe /FI "WINDOWTITLE eq pyclide*"  # Windows

# Clean registry
rm ~/.pyclide/servers.json
```

### Slow Performance (Cache Not Working)

Check server health:
```bash
# Health endpoint
curl http://127.0.0.1:PORT/health

# Should show:
# - cache_size > 0 (after first queries)
# - uptime > 0
# - status: "ok"
```

Restart server:
```bash
# Send shutdown
curl -X POST http://127.0.0.1:PORT/shutdown

# Next query will start fresh server
```

### Cache Out of Sync

File watcher should auto-invalidate cache, but if you see stale results:

```bash
# Restart server to clear cache
curl -X POST http://127.0.0.1:PORT/shutdown
```

Or wait 30 minutes for auto-shutdown.

### GitHub Connection Issues

If server fails to download:

```bash
# Check internet connection
ping github.com

# Verify GitHub access
git ls-remote https://github.com/GiampaoloGabba/pyclide

# Clear uvx cache and retry
rm -rf ~/.local/share/uv/cache/
```

## Security Notes

- Server binds to `127.0.0.1` (localhost only)
- No authentication (assumes local trusted environment)
- Server auto-shuts down after inactivity
- File watcher respects .gitignore (won't analyze secrets)

**DO NOT expose server to network** - it's designed for local-only use.

## Documentation

- **[SKILL.md](skills/pyclide/SKILL.md)** - Concise skill reference for Claude
- **[REFERENCE.md](skills/pyclide/REFERENCE.md)** - Complete command documentation

## License

MIT License - see source files for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Run test suite: `pytest`
5. Submit a pull request

## Credits

- **Jedi** - Python static analysis and code completion
- **Rope** - Python refactoring library
- **FastAPI** - Modern async web framework
- **Uvicorn** - Lightning-fast ASGI server
- **Watchdog** - Cross-platform filesystem monitoring

---

**Built for Claude Code** - High-performance Python semantic analysis with persistent hot cache
