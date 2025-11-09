# PyCLIDE Server: Implementation Plan

## Objective

Transform PyCLIDE from one-shot CLI to persistent client-server architecture for 10-20x performance improvement while maintaining full backward compatibility.

**Target**: Reduce latency from 300-1000ms to 20-50ms for repeated queries via hot RAM cache.

---

## 1. Problem Analysis

### 1.1 CLI One-Shot Performance Overhead

**Per-command overhead breakdown**:
```
$ pyclide defs app.py 10 5 --root .

Timeline:
[0ms]    Process start
[50ms]   Python interpreter loaded
[150ms]  Libraries imported (typer, jedi, rope)
[450ms]  Disk cache loaded (~/.cache/jedi/)
[500ms]  Jedi analyzes file + imports
[800ms]  Result returned
[820ms]  Process terminates, RAM released

Total: 820ms
Components:
  - Python startup: 50-100ms
  - Import overhead: 100-200ms
  - Disk cache load: 100-300ms
  - Query execution: 50-500ms
```

**Cache inefficiency**:
- Jedi/Rope cache stored on **disk** (`~/.cache/jedi/`, `.ropeproject/`)
- Every invocation rebuilds RAM state from disk
- "Warm" disk cache vs "hot" RAM cache

**Efficiency**: 37% (63% wasted on startup overhead)

### 1.2 Performance Comparison

| Approach | First query | Subsequent queries | 10 queries |
|----------|-------------|-------------------|------------|
| **LSP (Pylance)** | 100ms | 20-50ms (hot) | ~400ms |
| **PyCLIDE CLI** | 800ms | 700ms (always cold) | ~7000ms |
| **PyCLIDE Server** (target) | 800ms | 20-50ms (hot) | ~500ms |

**Improvement potential**: 14x on repeated operations

---

## 2. Architecture

### 2.1 System Overview

```
┌───────────────────────────────────────────────────────────────┐
│  Claude Code                                                   │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  Skill: .claude-plugin/skills/pyclide/                 │   │
│  │  └─ pyclide_client.py (single file, stdlib only)      │   │
│  └──────────────────────┬────────────────────────────────┘   │
└─────────────────────────┼────────────────────────────────────┘
                          │ python pyclide_client.py defs ...
                          ▼
┌───────────────────────────────────────────────────────────────┐
│  Client (pyclide_client.py)                                   │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  • Server lifecycle management                        │    │
│  │  • HTTP client (urllib.request)                       │    │
│  │  • Server registry (~/.pyclide/servers.json)          │    │
│  │  • Zero external dependencies                         │    │
│  └──────────────────────┬───────────────────────────────┘    │
└─────────────────────────┼───────────────────────────────────┘
                          │ uvx pyclide-server --root . --port 5001
                          │ (downloads from PyPI if needed)
                          ▼
┌───────────────────────────────────────────────────────────────┐
│  pyclide-server (per workspace, from PyPI via uvx)            │
│  ┌────────────────┬──────────────────┬────────────────────┐  │
│  │ HTTP Server    │ Hot Cache        │ File Watcher       │  │
│  │ (FastAPI)      │ (RAM)            │ (Invalidation)     │  │
│  ├────────────────┼──────────────────┼────────────────────┤  │
│  │ Port: 5001     │ • Jedi Scripts   │ • Monitor *.py     │  │
│  │ Workspace:     │ • Rope Project   │ • Detect changes   │  │
│  │ /project-a     │ • Symbol Index   │ • Invalidate cache │  │
│  │ PID: 12345     │ • AST Cache      │ • Re-analyze       │  │
│  └────────────────┴──────────────────┴────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

**Key architecture points**:
- Client: Single Python file (~10KB) in skill directory, uses stdlib only
- Server: PyPI package deployed via uvx, auto-downloaded on first use
- Multi-workspace: Isolated server per project, dynamic port allocation (5000-6000)
- Distribution: Client bundled with skill, server from PyPI (never in skill)

### 2.2 Design Principles

1. **Skill-native**: Client as single Python file in skill directory, invokable by Claude Code
2. **Zero dependencies**: Client uses stdlib only (json, urllib, subprocess, socket)
3. **Separation of concerns**: Heavy dependencies (FastAPI, Jedi, Rope) isolated in server via uvx
4. **Transparency**: Same command interface, server lifecycle managed automatically
5. **Workspace isolation**: One server per project, zero conflicts
6. **Auto-lifecycle**: Server start/stop managed by client, user unaware
7. **Cache consistency**: File watcher maintains cache synchronization

---

## 3. Core Components

### 3.1 HTTP Server (pyclide-server)

**Stack**:
- FastAPI (async HTTP framework)
- Uvicorn (ASGI server)
- asyncio (concurrency)

**Implementation**:
```python
# pyclide_server/server.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import jedi
from rope.base.project import Project
import uvicorn

class PyCLIDEServer:
    def __init__(self, workspace_root: str, port: int):
        self.root = Path(workspace_root).resolve()
        self.port = port
        self.app = FastAPI()

        # Hot state in RAM
        self.jedi_cache: Dict[str, jedi.Script] = {}
        self.rope_project: Project = Project(str(self.root))
        self.symbol_index: Dict[str, List[Location]] = {}

        # File watcher for cache invalidation
        self.file_watcher = FileWatcher(self.root, self.on_file_changed)

        # Health monitoring
        self.last_activity = time.time()
        self.request_count = 0

        self._setup_routes()
        self._start_file_watcher()
        self._start_health_monitor()

    def _setup_routes(self):
        @self.app.post("/defs")
        async def goto_definition(req: DefsRequest):
            self.last_activity = time.time()
            self.request_count += 1

            # Hot cache lookup
            script = self._get_cached_script(req.file)
            results = script.goto(req.line, req.col)
            return jedi_to_locations(results)

        @self.app.get("/health")
        async def health_check():
            return {
                "status": "ok",
                "workspace": str(self.root),
                "uptime": time.time() - self.start_time,
                "requests": self.request_count,
                "cache_size": len(self.jedi_cache)
            }

    def _get_cached_script(self, file_path: str) -> jedi.Script:
        """Get Script from hot cache or create new"""
        abs_path = str((self.root / file_path).resolve())

        if abs_path not in self.jedi_cache:
            self.jedi_cache[abs_path] = jedi.Script(path=abs_path)

        return self.jedi_cache[abs_path]

    def on_file_changed(self, file_path: str):
        """Callback from file watcher - invalidate cache"""
        abs_path = str((self.root / file_path).resolve())

        # Invalidate Jedi cache
        if abs_path in self.jedi_cache:
            del self.jedi_cache[abs_path]

        # Rope auto-detects changes, force validation
        self.rope_project.validate()

        # Invalidate symbol index
        self._invalidate_symbol_index(file_path)

        self.cache_invalidations += 1

    def start(self):
        self.start_time = time.time()
        uvicorn.run(
            self.app,
            host="127.0.0.1",
            port=self.port,
            log_level="warning"
        )
```

**API Endpoints**:
```
POST /defs              - Go to definition
POST /refs              - Find references
POST /hover             - Symbol information
POST /occurrences       - Semantic occurrences (Rope)
POST /rename            - Semantic rename
POST /extract-method    - Extract method refactor
POST /extract-var       - Extract variable refactor
POST /move              - Move symbol/module
POST /organize-imports  - Organize imports
POST /list              - List symbols
POST /grep              - Text search
POST /codemod           - AST transformations

GET  /health            - Health check
GET  /stats             - Server statistics
POST /shutdown          - Graceful shutdown
```

### 3.2 Client Script (pyclide_client.py)

**Single-file Python script**: Uses stdlib only, no external dependencies.

```python
#!/usr/bin/env python3
"""
PyCLIDE Client - Single-file script for Claude Code skill
Zero external dependencies (stdlib only)
"""

import json
import subprocess
import sys
import socket
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

# ============================================================================
# Server Registry
# ============================================================================

def get_registry_path() -> Path:
    """Get server registry path"""
    return Path.home() / ".pyclide" / "servers.json"

def load_registry() -> dict:
    """Load server registry"""
    registry_file = get_registry_path()
    if not registry_file.exists():
        return {"servers": []}
    with open(registry_file, 'r') as f:
        return json.load(f)

def save_registry(data: dict):
    """Save server registry"""
    registry_file = get_registry_path()
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    with open(registry_file, 'w') as f:
        json.dump(data, f, indent=2)

def find_server(workspace_root: str) -> dict | None:
    """Find server for workspace"""
    registry = load_registry()
    workspace_root = str(Path(workspace_root).resolve())
    for server in registry["servers"]:
        if server["workspace_root"] == workspace_root:
            return server
    return None

# ============================================================================
# Port Management
# ============================================================================

def is_port_available(port: int) -> bool:
    """Check if port is available"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', port))
            return True
    except OSError:
        return False

def allocate_port() -> int:
    """Allocate available port in range 5000-6000"""
    for port in range(5000, 6000):
        if is_port_available(port):
            return port
    raise RuntimeError("No available ports in range 5000-6000")

# ============================================================================
# Server Lifecycle
# ============================================================================

def is_server_healthy(server_info: dict) -> bool:
    """Check if server is responsive"""
    try:
        url = f"http://127.0.0.1:{server_info['port']}/health"
        req = Request(url)
        with urlopen(req, timeout=1.0) as response:
            return response.status == 200
    except (URLError, OSError):
        return False

def start_server_via_uvx(workspace_root: str) -> dict:
    """Start server via uvx (downloads from PyPI if needed)"""
    # Check uvx availability
    if subprocess.run(["uvx", "--version"], capture_output=True).returncode != 0:
        print("Error: uvx not found. Install: pip install uv", file=sys.stderr)
        sys.exit(1)

    port = allocate_port()

    # Start server in background via uvx
    cmd = [
        "uvx",
        "pyclide-server",  # PyPI package name
        "--root", workspace_root,
        "--port", str(port),
        "--daemon"
    ]

    if sys.platform == "win32":
        subprocess.Popen(
            cmd,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    else:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

    # Wait for server ready
    server_info = {
        "workspace_root": str(Path(workspace_root).resolve()),
        "port": port,
        "started_at": time.time()
    }

    for _ in range(20):  # 2 seconds max
        if is_server_healthy(server_info):
            registry = load_registry()
            registry["servers"].append(server_info)
            save_registry(registry)
            return server_info
        time.sleep(0.1)

    raise RuntimeError("Server failed to start")

def get_or_start_server(workspace_root: str) -> dict:
    """Get existing server or start new one"""
    server_info = find_server(workspace_root)
    if server_info and is_server_healthy(server_info):
        return server_info
    return start_server_via_uvx(workspace_root)

# ============================================================================
# HTTP Client
# ============================================================================

def send_request(server_info: dict, endpoint: str, data: dict) -> dict:
    """Send HTTP request to server using urllib"""
    url = f"http://127.0.0.1:{server_info['port']}/{endpoint}"
    json_data = json.dumps(data).encode('utf-8')
    req = Request(url, data=json_data, headers={'Content-Type': 'application/json'})

    try:
        with urlopen(req, timeout=10.0) as response:
            return json.loads(response.read().decode('utf-8'))
    except URLError as e:
        print(f"Error: Server communication failed: {e}", file=sys.stderr)
        sys.exit(1)

# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python pyclide_client.py <command> [args...]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    # Parse --root flag
    root = "."
    if "--root" in sys.argv:
        idx = sys.argv.index("--root")
        root = sys.argv[idx + 1]

    # Get or start server
    server_info = get_or_start_server(root)

    # Route command (example: defs)
    if command == "defs":
        file_path = sys.argv[2]
        line = int(sys.argv[3])
        col = int(sys.argv[4])

        result = send_request(server_info, "defs", {
            "file": file_path,
            "line": line,
            "col": col,
            "root": root
        })

        print(json.dumps(result))

if __name__ == "__main__":
    main()
```

**Key features**:
- Single file (~300 lines)
- Zero external dependencies (stdlib only)
- Server startup via `uvx pyclide-server`
- HTTP client using `urllib.request`
- Server registry in `~/.pyclide/servers.json`

### 3.3 Server Registry

**Storage**: `~/.pyclide/servers.json`

```json
{
  "servers": [
    {
      "workspace_root": "/home/user/project-a",
      "port": 5001,
      "pid": 12345,
      "started_at": "2025-01-08T10:00:00Z",
      "last_activity": "2025-01-08T10:45:30Z"
    }
  ]
}
```

**Implementation**:
```python
class ServerRegistry:
    def __init__(self):
        self.registry_file = Path.home() / ".pyclide" / "servers.json"
        self.registry_file.parent.mkdir(exist_ok=True)

    def get(self, workspace_root: Path) -> Optional[ServerInfo]:
        data = self._load()
        for entry in data["servers"]:
            if Path(entry["workspace_root"]) == workspace_root:
                return ServerInfo.from_dict(entry)
        return None

    def cleanup_dead_servers(self):
        """Remove entries for dead processes"""
        data = self._load()
        alive = [s for s in data["servers"] if psutil.pid_exists(s["pid"])]
        data["servers"] = alive
        self._save(data)
```

### 3.4 Port Allocation

**Strategy**: Dynamic allocation in 5000-6000 range.

```python
PORT_RANGE = range(5000, 6000)

def allocate_port() -> int:
    """Find available port in range"""
    registry = ServerRegistry()
    used_ports = {s.port for s in registry.get_all()}

    for port in PORT_RANGE:
        if port not in used_ports and not is_port_in_use(port):
            return port

    raise RuntimeError("No available ports in range 5000-6000")


def is_port_in_use(port: int) -> bool:
    """Check if port is bound"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', port))
            return False
    except OSError:
        return True
```

### 3.5 Deployment Model

**Architecture**: Client bundled with skill, server from PyPI via uvx.

**Client Distribution**:
```
.claude-plugin/skills/pyclide/
├── SKILL.md              # Skill definition
├── REFERENCE.md          # Command documentation
└── pyclide_client.py     # Single-file client (~10KB)
```

**Server Distribution**:
- Published to PyPI as `pyclide-server`
- Downloaded automatically by uvx on first use
- Cached in uvx's isolated environment
- Never included in skill directory

**First Invocation Flow**:
```bash
# Claude Code executes:
python .claude-plugin/skills/pyclide/pyclide_client.py defs app.py 10 5

# Client detects no server running
# Client executes: uvx pyclide-server --root . --port 5001 --daemon

# uvx checks cache (~/.local/share/uv/cache/)
# If not cached: downloads pyclide-server from PyPI
# If cached: uses cached version

# Server starts in background
# Client sends HTTP request to server
# Returns result to Claude Code
```

**Subsequent Invocations**:
```bash
# Claude Code executes same command
# Client finds existing server (via registry)
# Sends HTTP request immediately
# 20-50ms response (hot cache)
```

**Benefits**:
- Minimal skill size (~10KB client vs ~50MB if bundled)
- Server updates via PyPI (no skill redistribution)
- Zero user setup (uvx handles dependencies)
- Isolated environments per server version
- Offline support (after first download)

**Requirements**:
- User must have `uv` installed (`pip install uv`)
- Python 3.8+ (implied for Python development)
- Internet connection (first download only)

---

## 4. File Watcher (Critical Component)

### 4.1 Requirements

**Problem**: Cache invalidation across multiple modification sources.

**Modification sources**:
1. Claude Code tools (Edit, Write)
2. User's IDE (VS Code, PyCharm, etc.)
3. PyCLIDE refactorings (rename, extract, organize-imports)
4. External scripts (git pull, build systems)

**Consequence without watcher**: Stale cache → incorrect results.

### 4.2 Implementation

**Technology**: `watchdog` library (cross-platform filesystem monitoring)

```python
# pyclide_server/file_watcher.py

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from pathlib import Path
from typing import Callable

class PythonFileWatcher:
    """
    Monitor workspace for Python file changes.
    Notify server to invalidate cache on modifications.
    """

    def __init__(self, workspace_root: Path, on_change_callback: Callable[[str], None]):
        self.root = workspace_root
        self.on_change = on_change_callback
        self.observer = Observer()

        # Debouncing: avoid multiple notifications for same modification
        self.last_modified: Dict[str, float] = {}
        self.debounce_seconds = 0.1

        # Ignore patterns (hardcoded + .gitignore)
        self._setup_ignore_patterns()

    def _setup_ignore_patterns(self):
        """Setup ignore patterns from hardcoded list + .gitignore"""
        # Hardcoded patterns
        self.hardcoded_ignore = [
            '**/__pycache__/**',
            '**/.venv/**',
            '**/venv/**',
            '**/env/**',
            '**/.git/**',
            '**/*.pyc',
            '**/*.pyo',
            '**/*.swp',
            '**/*.tmp',
            '**/node_modules/**',
            '**/.pytest_cache/**',
            '**/.mypy_cache/**',
            '**/.ruff_cache/**',
        ]

        # Load .gitignore if exists
        self.gitignore_spec = None
        gitignore_path = self.root / ".gitignore"
        if gitignore_path.exists():
            import pathspec
            with open(gitignore_path, 'r') as f:
                patterns = f.readlines()
            self.gitignore_spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)

    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored"""
        from fnmatch import fnmatch

        # Check hardcoded patterns
        for pattern in self.hardcoded_ignore:
            if fnmatch(path, pattern):
                return True

        # Check .gitignore patterns
        if self.gitignore_spec:
            rel_path = Path(path).relative_to(self.root)
            if self.gitignore_spec.match_file(str(rel_path)):
                return True

        return False

    def start(self):
        """Start monitoring filesystem"""
        handler = PythonFileHandler(self._on_file_event)
        self.observer.schedule(handler, str(self.root), recursive=True)
        self.observer.start()

    def stop(self):
        """Stop monitoring"""
        self.observer.stop()
        self.observer.join()

    def _on_file_event(self, event: FileSystemEvent):
        """Handle file modification event"""
        if event.is_directory:
            return

        if not event.src_path.endswith('.py'):
            return

        if self._should_ignore(event.src_path):
            return

        # Debouncing
        now = time.time()
        if event.src_path in self.last_modified:
            if now - self.last_modified[event.src_path] < self.debounce_seconds:
                return

        self.last_modified[event.src_path] = now

        # Notify server
        rel_path = Path(event.src_path).relative_to(self.root)
        self.on_change(str(rel_path))


class PythonFileHandler(FileSystemEventHandler):
    """Handler for filesystem events"""

    def __init__(self, callback: Callable[[FileSystemEvent], None]):
        self.callback = callback

    def on_modified(self, event):
        self.callback(event)

    def on_created(self, event):
        self.callback(event)

    def on_deleted(self, event):
        self.callback(event)

    def on_moved(self, event):
        self.callback(event)
```

### 4.3 .gitignore Integration

**Library**: `pathspec` (implements Git wildmatch rules exactly)

**Dependency**: Add `pathspec>=0.11.0` to requirements

**Rationale**:
- If file is gitignored, it's typically not source code (build artifacts, venv, secrets)
- User intent already expressed via .gitignore
- Significant performance gain (avoid monitoring thousands of files in venv/)

**Future**: `.pyclideignore` file for custom ignore patterns (v2.0+)

---

## 5. Health Monitoring & Auto-Restart

### 5.1 Health Monitor

**Responsibilities**:
- Detect server hang/crash
- Auto-restart on failure
- Inactivity timeout (30min)
- Memory monitoring

**Implementation**:
```python
# pyclide_server/health.py

import asyncio
import psutil

class HealthMonitor:
    def __init__(self, server: 'PyCLIDEServer'):
        self.server = server
        self.check_interval = 30  # seconds
        self.inactivity_timeout = 1800  # 30 minutes
        self.error_threshold = 5
        self.memory_limit_mb = 500

        self.consecutive_errors = 0

    async def start(self):
        """Start health monitoring loop"""
        while True:
            await asyncio.sleep(self.check_interval)

            try:
                await self._health_check()
            except Exception as e:
                logging.error(f"Health check error: {e}")
                self.consecutive_errors += 1

                if self.consecutive_errors >= self.error_threshold:
                    await self._graceful_shutdown()

    async def _health_check(self):
        """Perform health checks"""

        # Check inactivity timeout
        inactive_seconds = time.time() - self.server.last_activity
        if inactive_seconds > self.inactivity_timeout:
            logging.info(f"Inactive for {inactive_seconds}s, shutting down")
            await self._graceful_shutdown()
            return

        # Check memory usage
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        if memory_mb > self.memory_limit_mb:
            logging.warning(f"High memory: {memory_mb}MB, triggering cleanup")
            self.server.cleanup_cache()

        # Validate Jedi/Rope state
        test_file = self.server.root / "test.py"
        if test_file.exists():
            jedi.Script(path=str(test_file))

        # Reset error counter on success
        self.consecutive_errors = 0

    async def _graceful_shutdown(self):
        """Shutdown server gracefully"""
        if hasattr(self.server, 'file_watcher'):
            self.server.file_watcher.stop()

        registry = ServerRegistry()
        registry.remove(self.server.root)

        import sys
        sys.exit(0)
```

### 5.2 Client-Side Auto-Restart

**Strategy**: Retry with automatic server restart on failure.

```python
def send_to_server_with_retry(server_info, args, max_retries=2):
    """Send request with auto-retry on failure"""

    for attempt in range(max_retries):
        try:
            return send_to_server(server_info, args)
        except (ConnectionError, requests.RequestException) as e:
            if attempt < max_retries - 1:
                logging.warning(f"Server failed (attempt {attempt+1}), restarting...")

                # Kill old server
                if psutil.pid_exists(server_info.pid):
                    psutil.Process(server_info.pid).terminate()

                # Remove from registry
                ServerRegistry().remove(server_info.root)

                # Start new server
                server_info = get_or_start_server(args.root)
                time.sleep(0.5)
            else:
                raise ServerError(f"Server failed after {max_retries} attempts")
```

---

## 6. Performance Targets

### 6.1 Benchmark Objectives

| Scenario | CLI Current | Server Target | Improvement |
|----------|-------------|---------------|-------------|
| Cold start (first query) | 800ms | 800ms | - |
| Hot cache (second query) | 700ms | 20-50ms | **14-35x** |
| 10 queries in session | 7000ms | 500ms | **14x** |
| Find references (10k LOC) | 1500ms | 100-200ms | **7-15x** |
| Complex rename | 2000ms | 200-400ms | **5-10x** |

### 6.2 Memory Footprint

**Per-workspace server**:
- Python process base: ~30MB
- Jedi cache (100 files): ~20-40MB
- Rope project model: ~10-30MB
- Symbol index: ~5-20MB
- **Total**: ~50-120MB per workspace

**Multi-workspace**: 5 projects = ~250-600MB total (acceptable for modern systems)

---

## 7. Implementation Phases

### Phase 1: Server Core (MVP)

**Deliverable**: Functioning server with core commands.

**Tasks**:
- [ ] Setup FastAPI + Uvicorn
- [ ] Implement endpoints: `/defs`, `/refs`, `/hover`, `/rename`
- [ ] Hot cache (Jedi dict in RAM)
- [ ] Rope integration
- [ ] Health endpoint (`/health`)
- [ ] Daemon mode (background process)

**Validation**:
```bash
# Start server manually
python -m pyclide_server --root . --port 5001

# Test via curl
curl -X POST http://localhost:5001/defs \
  -H "Content-Type: application/json" \
  -d '{"file": "app.py", "line": 10, "col": 5, "root": "."}'
```

### Phase 2: Client Integration

**Deliverable**: Single-file client with stdlib-only implementation.

**Tasks**:
- [ ] Create `pyclide_client.py` as single file
- [ ] Implement server registry (stdlib: json, pathlib)
- [ ] Implement port allocation (stdlib: socket)
- [ ] Implement HTTP client (stdlib: urllib.request)
- [ ] Implement `start_server_via_uvx()` function
- [ ] Implement `get_or_start_server()` function
- [ ] Cross-platform background process spawning
- [ ] Health check using HTTP GET /health
- [ ] Command routing (defs, refs, hover, etc.)

**Validation**:
```bash
# Claude Code invokes:
python skills/pyclide/pyclide_client.py defs app.py 10 5 --root .

# First invocation:
# - Client detects no server
# - Executes: uvx pyclide-server --root . --port 5001 --daemon
# - uvx downloads from PyPI (first time)
# - Waits for server ready
# - Sends HTTP request
# - Returns JSON result

# Subsequent invocations:
# - Client finds server in registry
# - Sends HTTP request immediately
# - Returns JSON result (20-50ms)
```

### Phase 3: File Watcher

**Deliverable**: Cache remains synchronized with filesystem.

**Tasks**:
- [ ] Integrate `watchdog` library
- [ ] Monitor `*.py` files recursively
- [ ] Debouncing logic
- [ ] Hardcoded ignore patterns
- [ ] .gitignore integration via `pathspec`
- [ ] Cache invalidation on file change

**Validation**:
```bash
# Query file
pyclide defs app.py 10 5

# Modify file in IDE
echo "# comment" >> app.py

# Re-query - cache automatically invalidated
pyclide defs app.py 10 5  # Reflects new state
```

### Phase 4: Health Monitoring

**Deliverable**: Server auto-manages lifecycle.

**Tasks**:
- [ ] Inactivity timeout (30min)
- [ ] Memory monitoring
- [ ] Error tracking
- [ ] Graceful shutdown
- [ ] Client-side auto-restart

**Validation**:
```bash
# Start server, leave idle 30min
pyclide defs app.py 10 5
# (wait 30 minutes)

# Server auto-shutdown (check registry)

# New command restarts server transparently
pyclide refs app.py 20 10
```

### Phase 5: Optimization & Testing

**Deliverable**: Production-ready system.

**Tasks**:
- [ ] Performance benchmarks (<50ms target)
- [ ] Multi-workspace testing
- [ ] Edge cases:
  - Port conflicts
  - Server crash during request
  - File watcher race conditions
  - Large projects (10k+ files)
- [ ] Memory optimization (cache size limits)
- [ ] Logging configuration

### Phase 6: Documentation

**Tasks**:
- [ ] Update SKILL.md (server mode note)
- [ ] Update README.md (installation, troubleshooting)
- [ ] Create ARCHITECTURE.md (server design)
- [ ] Create TROUBLESHOOTING.md (server issues)

---

## 8. Project Structure

```
python-semantic-ide/
├── pyclide_server/              # Server package (published to PyPI)
│   ├── __init__.py
│   ├── __main__.py              # Entry point: uvx pyclide-server
│   ├── server.py                # PyCLIDEServer class (FastAPI)
│   ├── file_watcher.py          # FileWatcher with watchdog
│   ├── health.py                # HealthMonitor
│   └── pyproject.toml           # Server dependencies
│
├── skills/pyclide/              # Claude Code skill (bundled with skill)
│   ├── SKILL.md                 # Skill definition
│   ├── REFERENCE.md             # Command documentation
│   └── pyclide_client.py        # Single-file client (stdlib only)
│
├── docs/
│   ├── PYCLIDE_SERVER_PLAN.md   # This file
│   ├── ARCHITECTURE.md          # Server architecture
│   └── TROUBLESHOOTING.md       # Debugging guide
│
├── tests/
│   ├── test_client.py           # Client tests
│   ├── test_server.py           # Server tests
│   └── test_integration.py      # End-to-end tests
│
└── README.md                    # Installation and usage
```

**Key points**:
- `pyclide_server/`: Published to PyPI as `pyclide-server` package
- `skills/pyclide/`: Distributed with Claude Code skill
- `pyclide_client.py`: Single file, zero dependencies, ~300 lines
- No `scripts/` directory (client is invoked directly by skill)
- No `pyclide_client/` package (single file sufficient)

---

## 9. Dependencies

### Client Dependencies

**ZERO external dependencies** - stdlib only:
```python
# pyclide_client.py uses only:
import json              # JSON serialization
import subprocess        # Server process management
import sys               # CLI argument parsing
import socket            # Port availability checks
import time              # Timing and delays
from pathlib import Path # File path handling
from urllib.request import urlopen, Request  # HTTP client
from urllib.error import URLError            # HTTP error handling
```

**Why stdlib-only?**
- Minimal skill size (~10KB)
- Zero installation overhead
- Works on any Python 3.8+ installation
- No dependency conflicts

### Server Dependencies

**Full requirements** (managed by uvx, never in skill):
```toml
# pyclide_server/pyproject.toml
[project]
name = "pyclide-server"
version = "1.0.0"
dependencies = [
    "fastapi>=0.104.0",           # HTTP server framework
    "uvicorn[standard]>=0.24.0",  # ASGI server
    "jedi>=0.19.0",               # Python code analysis
    "rope>=1.11.0",               # Python refactoring
    "watchdog>=3.0.0",            # Filesystem monitoring
    "pathspec>=0.11.0",           # .gitignore parsing
]
```

**Deployment**:
- Published to PyPI as `pyclide-server`
- Downloaded by uvx on first use
- Isolated in uvx cache (~/.local/share/uv/)
- Never bundled with skill

---

## 10. Compatibility & Requirements

### 10.1 API Compatibility

**Guarantees**:
1. Command interface unchanged (same args, same JSON output)
2. Skill invocation unchanged (`python pyclide_client.py defs ...`)
3. All existing commands work identically
4. Output format backward compatible

**Example**:
```bash
# Before (one-shot CLI):
python pyclide.py defs app.py 10 5 --root .

# After (client-server):
python pyclide_client.py defs app.py 10 5 --root .

# Output format: identical JSON
```

### 10.2 System Requirements

**User environment**:
- Python 3.8+ (required for Claude Code usage)
- `uv` package manager (`pip install uv`)
- Internet connection (first server download only)

**Automatic setup**:
- Client: Bundled with skill, no installation
- Server: Downloaded automatically via uvx on first use
- No manual configuration required

### 10.3 Error Handling

**uvx not available**:
```bash
Error: uvx not found. Install with:
  pip install uv
or visit: https://docs.astral.sh/uv/
```

**Server startup failure**:
- Client retries once with new server instance
- Clear error message if retry fails
- User can manually troubleshoot via `uvx pyclide-server --help`

---

## 11. Risk Management

### 11.1 Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Server crash during query | High | Client auto-restart |
| Cache stale (watcher miss) | High | Watchdog reliable + debouncing + .gitignore |
| Port conflicts | Medium | 1000-port range, fallback CLI |
| Memory leak | Medium | Health monitor + auto-shutdown |
| Cross-platform issues | High | Testing on Win/Linux/Mac |

### 11.2 Operational Risks

| Risk | Mitigation |
|------|------------|
| Background processes confuse user | Clear docs, `pyclide server status` command |
| Too many servers in RAM | Auto-shutdown after inactivity |
| Debugging difficulty | Detailed logging, `--debug` flag |

---

## 12. Success Metrics

**KPIs**:
1. **Performance**: 90% queries <50ms after warm-up
2. **Reliability**: <1% fallback to CLI mode
3. **Memory**: <150MB RAM per workspace
4. **Uptime**: Server stable until inactivity timeout

**Testing**:
- Unit tests: Component isolation
- Integration tests: Client ↔ Server full flow
- Performance tests: Benchmark on 10k LOC project
- Stress tests: 1000 consecutive queries

---

## 13. Future Enhancements (v2.0+)

### .pyclideignore File

**Purpose**: Custom ignore patterns beyond .gitignore.

**Use case**: User wants to analyze vendored code in git but exclude from PyCLIDE cache.

**Format**:
```
# .pyclideignore
vendored/
legacy_*.py
experiments/
```

**Implementation**: Load alongside .gitignore, merge patterns.

**Priority**: Low (most needs covered by .gitignore)

### Pre-built Symbol Index

**Optimization**: Build symbol index on server start for instant lookups.

**Trade-off**: Slower startup (~2-5s) vs faster queries (5-10ms).

### Remote Server Support

**Use case**: Network-shared server for team workspace.

**Complexity**: High (security, auth, network reliability).

---

## 14. Implementation Checklist

**Phase 1: Server Core**
- [ ] FastAPI server setup
- [ ] Core endpoints (defs, refs, hover, rename)
- [ ] Jedi/Rope hot cache
- [ ] Health endpoint
- [ ] Daemon mode

**Phase 2: Client Integration**
- [ ] Server registry
- [ ] Port allocation
- [ ] Auto-start logic
- [ ] Health check
- [ ] CLI fallback

**Phase 3: File Watcher**
- [ ] Watchdog integration
- [ ] Debouncing
- [ ] Hardcoded ignore patterns
- [ ] .gitignore support via pathspec
- [ ] Cache invalidation

**Phase 4: Health Monitoring**
- [ ] Inactivity timeout
- [ ] Memory monitoring
- [ ] Error tracking
- [ ] Auto-restart (client-side)

**Phase 5: Testing**
- [ ] Performance benchmarks
- [ ] Multi-workspace tests
- [ ] Edge case testing
- [ ] Cross-platform validation

**Phase 6: Documentation**
- [ ] Update SKILL.md
- [ ] Update README.md
- [ ] Create ARCHITECTURE.md
- [ ] Create TROUBLESHOOTING.md
