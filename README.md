# PyCLIDE: Python Command-Line IDE

**High-performance Python semantic analysis and refactoring** with client-server architecture for 10-20x faster repeated operations.

Provides IDE-quality code analysis using Jedi (navigation) and Rope (refactoring) with **persistent hot cache** for instant responses.

## Architecture

PyCLIDE uses a **client-server architecture** for optimal performance:

- **Client**: Lightweight Python script (stdlib only) bundled with Claude Code skill
- **Server**: Background process with hot RAM cache (auto-downloaded from GitHub via uvx)
- **Performance**:
  - First query: ~800ms (cold start)
  - Subsequent queries: **20-50ms** (hot cache)
  - **14x faster** than one-shot CLI for repeated operations

### How It Works

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

**Key features**:
- One server per workspace (isolated environments)
- Auto-start on first use (transparent to user)
- File watcher maintains cache consistency
- Auto-shutdown after 30 minutes inactivity

## Features

### Navigation (Jedi-based)
- **Go to definition** - Jump to where symbols are defined
- **Find references** - Find all usages of a symbol
- **Hover information** - Get type, signature, and docstrings

### Refactoring (Rope-based)
- **Semantic rename** - Rename with automatic import updates
- **Extract method/variable** - Refactor code into reusable components
- **Move symbols** - Reorganize code between files
- **Organize imports** - Clean up and normalize imports
- **Semantic occurrences** - Find references within rename scope

### Utilities
- **List symbols** - Quick overview of classes/functions (AST-based, fast)
- **AST codemods** - Mass transformations with ast-grep (optional)

**Note:** For text search, use Claude Code's native Grep tool (built-in ripgrep integration).

## Installation

### Prerequisites

**Required:**
- Python 3.8+ (already required for Claude Code)
- `uv` package manager: `pip install uv`

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
4. **uvx downloads** `pyclide-server` from GitHub (first time only, ~5s)
5. **Server starts** in background
6. **Client sends HTTP request** to server
7. **Result returned** to Claude Code

Subsequent invocations use the running server (**20-50ms response time**).

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

## Documentation

- **[SKILL.md](skills/pyclide/SKILL.md)** - Concise skill reference for Claude
- **[REFERENCE.md](skills/pyclide/REFERENCE.md)** - Complete command documentation
- **[PYCLIDE_SERVER_PLAN.md](docs/PYCLIDE_SERVER_PLAN.md)** - Server architecture details
- **[TESTING_PLAN.md](docs/TESTING_PLAN.md)** - Comprehensive test plan

## Project Structure

```
python-semantic-ide/
├── pyclide.py                    # Original CLI (maintained for compatibility)
├── pyclide_server/               # Server package (published to PyPI)
│   ├── __init__.py
│   ├── __main__.py               # Entry point: pyclide-server
│   ├── server.py                 # FastAPI server with hot cache
│   ├── rope_engine.py            # Rope integration
│   ├── jedi_helpers.py           # Jedi integration
│   ├── file_watcher.py           # Cache invalidation
│   ├── health.py                 # Auto-shutdown monitoring
│   └── models.py                 # Pydantic request/response models
├── skills/pyclide/               # Claude Code skill
│   ├── SKILL.md                  # Skill definition
│   ├── REFERENCE.md              # Command reference
│   └── pyclide_client.py         # Client (~400 lines, stdlib only)
├── tests/                        # Test suite
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/                         # Documentation
│   ├── PYCLIDE_SERVER_PLAN.md
│   └── TESTING_PLAN.md
├── pyproject.toml                # PyPI package config
└── README.md                     # This file
```

## Performance

| Scenario | One-Shot CLI | Server (Hot Cache) | Improvement |
|----------|--------------|-------------------|-------------|
| First query | 800ms | 800ms | - |
| Second query | 700ms | **20-50ms** | **14-35x** |
| 10 queries | 7000ms | **500ms** | **14x** |
| Find refs (10k LOC) | 1500ms | **100-200ms** | **7-15x** |

**Memory footprint**: ~50-120MB per workspace (includes Python runtime, Jedi, Rope, caches)

## Development

### Running Server Locally

For development/testing without uvx:

```bash
# Install dependencies
pip install -e .  # Installs from pyproject.toml

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

**Client code** (`skills/pyclide/pyclide_client.py`):
1. Edit client (keep stdlib-only!)
2. Test: `python skills/pyclide/pyclide_client.py defs ...`
3. Update `SKILL.md` if command interface changes

**Original CLI** (`pyclide.py`):
- Maintained for backward compatibility
- Not used by skill (uses client-server instead)

## Distribution

### As Claude Code Skill

1. Copy `skills/pyclide/` to user's `~/.claude/skills/pyclide`
2. Server auto-downloads from GitHub on first use

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

### Alternative: Local Development Mode

For testing without GitHub, modify the client to use local installation:
```python
# In pyclide_client.py, replace:
# cmd = ["uvx", "--from", GITHUB_REPO, "pyclide-server", ...]
# with:
# cmd = ["python", "-m", "pyclide_server", ...]
```

## Known Limitations

### Server-Specific

**File Watcher**:
- Requires `watchdog` library (auto-installed with server)
- May miss changes to files ignored by .gitignore (by design)
- Debouncing (100ms) may delay cache invalidation slightly

**Auto-Shutdown**:
- Server shuts down after 30 minutes inactivity
- Next query will restart server (~800ms first request)
- Can be configured via environment variables (future)

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
- Preview changes before applying (client returns JSON patches)
- Run tests after refactoring
- Use `--force` flag for non-interactive mode

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

### "Module not found" Errors

Server dependencies missing:
```bash
# Install from GitHub
uvx --from git+https://github.com/GiampaoloGabba/pyclide pyclide-server --help

# Or install from source
git clone https://github.com/GiampaoloGabba/pyclide
cd pyclide
pip install -e .
```

## Security Notes

- Server binds to `127.0.0.1` (localhost only)
- No authentication (assumes local trusted environment)
- Server auto-shuts down after inactivity
- File watcher respects .gitignore (won't analyze secrets)

**DO NOT expose server to network** - it's designed for local-only use.

## License

MIT License - see source files for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Run test suite: `pytest`
5. Submit a pull request

See [TESTING_PLAN.md](docs/TESTING_PLAN.md) for test guidelines.

## Credits

- **Jedi** - Python static analysis and code completion
- **Rope** - Python refactoring library
- **FastAPI** - Modern async web framework
- **Uvicorn** - Lightning-fast ASGI server
- **Watchdog** - Cross-platform filesystem monitoring
- **Typer** - Modern CLI framework (original CLI)

## Support

- **Issues**: GitHub Issues
- **Documentation**: See `docs/` directory
- **Architecture**: [PYCLIDE_SERVER_PLAN.md](docs/PYCLIDE_SERVER_PLAN.md)
- **Testing**: [TESTING_PLAN.md](docs/TESTING_PLAN.md)

---

**Built for Claude Code** | High-performance Python semantic analysis with persistent hot cache
