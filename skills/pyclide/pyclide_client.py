#!/usr/bin/env python3
"""
PyCLIDE Client - Single-file script for Claude Code skill.

Zero external dependencies (stdlib only).
Manages server lifecycle and routes commands to pyclide-server.

Usage:
    python pyclide_client.py defs app.py 10 5 --root .
    python pyclide_client.py rename app.py 10 5 new_name --root .
"""

import json
import subprocess
import sys
import socket
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
from typing import Dict, Any, Optional, List

# ============================================================================
# Server Registry
# ============================================================================

def get_registry_path() -> Path:
    """Get server registry path."""
    return Path.home() / ".pyclide" / "servers.json"


def load_registry() -> Dict[str, Any]:
    """Load server registry."""
    registry_file = get_registry_path()
    if not registry_file.exists():
        return {"servers": []}
    with open(registry_file, 'r') as f:
        return json.load(f)


def save_registry(data: Dict[str, Any]) -> None:
    """Save server registry."""
    registry_file = get_registry_path()
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    with open(registry_file, 'w') as f:
        json.dump(data, f, indent=2)


def find_server(workspace_root: str) -> Optional[Dict[str, Any]]:
    """Find server for workspace."""
    registry = load_registry()
    workspace_root = str(Path(workspace_root).resolve())
    for server in registry["servers"]:
        if server["workspace_root"] == workspace_root:
            return server
    return None


def add_server(workspace_root: str, port: int) -> None:
    """Add server to registry."""
    registry = load_registry()
    server_info = {
        "workspace_root": str(Path(workspace_root).resolve()),
        "port": port,
        "started_at": time.time()
    }
    registry["servers"].append(server_info)
    save_registry(registry)


def remove_server(workspace_root: str) -> None:
    """Remove server from registry."""
    registry = load_registry()
    workspace_root = str(Path(workspace_root).resolve())
    registry["servers"] = [
        s for s in registry["servers"]
        if s["workspace_root"] != workspace_root
    ]
    save_registry(registry)


# ============================================================================
# Port Management
# ============================================================================

def is_port_available(port: int) -> bool:
    """Check if port is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', port))
            return True
    except OSError:
        return False


def allocate_port() -> int:
    """Allocate available port in range 5000-6000."""
    registry = load_registry()
    used_ports = {s["port"] for s in registry["servers"]}

    for port in range(5000, 6000):
        if port not in used_ports and is_port_available(port):
            return port

    raise RuntimeError("No available ports in range 5000-6000")


# ============================================================================
# Server Lifecycle
# ============================================================================

def is_server_healthy(server_info: Dict[str, Any]) -> bool:
    """Check if server is responsive."""
    try:
        url = f"http://127.0.0.1:{server_info['port']}/health"
        req = Request(url)
        with urlopen(req, timeout=1.0) as response:
            return response.status == 200
    except (URLError, OSError, Exception):
        return False


def check_uvx_available() -> bool:
    """Check if uvx is available."""
    try:
        result = subprocess.run(
            ["uvx", "--version"],
            capture_output=True,
            timeout=2.0
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def start_server_via_uvx(workspace_root: str) -> Dict[str, Any]:
    """Start server via uvx from GitHub repository."""
    # Check uvx availability
    if not check_uvx_available():
        print("Error: uvx not found. Install with: pip install uv", file=sys.stderr)
        print("or visit: https://docs.astral.sh/uv/", file=sys.stderr)
        sys.exit(1)

    port = allocate_port()

    # GitHub repository URL
    GITHUB_REPO = "git+https://github.com/GiampaoloGabba/pyclide"

    # Start server from GitHub in background
    cmd = [
        "uvx",
        "--from", GITHUB_REPO,
        "pyclide-server",
        "--root", workspace_root,
        "--port", str(port),
        "--daemon"
    ]

    try:
        if sys.platform == "win32":
            # Windows: detached process
            subprocess.Popen(
                cmd,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # Unix: new session
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
    except Exception as e:
        print(f"Error starting server: {e}", file=sys.stderr)
        sys.exit(1)

    # Wait for server ready (longer timeout for GitHub clone)
    server_info = {
        "workspace_root": str(Path(workspace_root).resolve()),
        "port": port,
        "started_at": time.time()
    }

    for attempt in range(30):  # 3 seconds max (GitHub download takes longer)
        if is_server_healthy(server_info):
            add_server(workspace_root, port)
            return server_info
        time.sleep(0.1)

    raise RuntimeError("Server failed to start from GitHub within 3 seconds")


def get_or_start_server(workspace_root: str) -> Dict[str, Any]:
    """Get existing server or start new one."""
    server_info = find_server(workspace_root)

    if server_info and is_server_healthy(server_info):
        return server_info

    # Server not found or unhealthy, remove from registry and start new one
    if server_info:
        remove_server(workspace_root)

    return start_server_via_uvx(workspace_root)


# ============================================================================
# HTTP Client
# ============================================================================

def send_request(server_info: Dict[str, Any], endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Send HTTP request to server using urllib."""
    url = f"http://127.0.0.1:{server_info['port']}/{endpoint}"
    json_data = json.dumps(data).encode('utf-8')
    req = Request(url, data=json_data, headers={'Content-Type': 'application/json'})

    try:
        with urlopen(req, timeout=10.0) as response:
            return json.loads(response.read().decode('utf-8'))
    except URLError as e:
        print(f"Error: Server communication failed: {e}", file=sys.stderr)
        # Try to restart server once
        remove_server(server_info["workspace_root"])
        print("Attempting to restart server...", file=sys.stderr)
        new_server = get_or_start_server(server_info["workspace_root"])
        # Retry request
        with urlopen(req, timeout=10.0) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error: Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


# ============================================================================
# Command Handlers
# ============================================================================

def handle_defs(args: List[str], root: str) -> None:
    """Handle 'defs' command (go to definition)."""
    if len(args) < 3:
        print("Usage: pyclide_client.py defs <file> <line> <col> [--root <root>]", file=sys.stderr)
        sys.exit(1)

    file_path, line, col = args[0], int(args[1]), int(args[2])
    server_info = get_or_start_server(root)

    result = send_request(server_info, "defs", {
        "file": file_path,
        "line": line,
        "col": col,
        "root": root
    })

    print(json.dumps(result, indent=2))


def handle_refs(args: List[str], root: str) -> None:
    """Handle 'refs' command (find references)."""
    if len(args) < 3:
        print("Usage: pyclide_client.py refs <file> <line> <col> [--root <root>]", file=sys.stderr)
        sys.exit(1)

    file_path, line, col = args[0], int(args[1]), int(args[2])
    server_info = get_or_start_server(root)

    result = send_request(server_info, "refs", {
        "file": file_path,
        "line": line,
        "col": col,
        "root": root
    })

    print(json.dumps(result, indent=2))


def handle_hover(args: List[str], root: str) -> None:
    """Handle 'hover' command (symbol information)."""
    if len(args) < 3:
        print("Usage: pyclide_client.py hover <file> <line> <col> [--root <root>]", file=sys.stderr)
        sys.exit(1)

    file_path, line, col = args[0], int(args[1]), int(args[2])
    server_info = get_or_start_server(root)

    result = send_request(server_info, "hover", {
        "file": file_path,
        "line": line,
        "col": col,
        "root": root
    })

    print(json.dumps(result, indent=2))


def handle_rename(args: List[str], root: str) -> None:
    """Handle 'rename' command (semantic rename)."""
    if len(args) < 4:
        print("Usage: pyclide_client.py rename <file> <line> <col> <new_name> [--root <root>]", file=sys.stderr)
        sys.exit(1)

    file_path, line, col, new_name = args[0], int(args[1]), int(args[2]), args[3]
    server_info = get_or_start_server(root)

    result = send_request(server_info, "rename", {
        "file": file_path,
        "line": line,
        "col": col,
        "new_name": new_name,
        "root": root
    })

    print(json.dumps(result, indent=2))


def handle_occurrences(args: List[str], root: str) -> None:
    """Handle 'occurrences' command (semantic occurrences)."""
    if len(args) < 3:
        print("Usage: pyclide_client.py occurrences <file> <line> <col> [--root <root>]", file=sys.stderr)
        sys.exit(1)

    file_path, line, col = args[0], int(args[1]), int(args[2])
    server_info = get_or_start_server(root)

    result = send_request(server_info, "occurrences", {
        "file": file_path,
        "line": line,
        "col": col,
        "root": root
    })

    print(json.dumps(result, indent=2))


# ============================================================================
# CLI Entry Point
# ============================================================================

def main() -> None:
    """Main entry point for pyclide_client."""
    if len(sys.argv) < 2:
        print("Usage: python pyclide_client.py <command> [args...] [--root <root>]", file=sys.stderr)
        print("\nCommands:", file=sys.stderr)
        print("  defs <file> <line> <col>           - Go to definition", file=sys.stderr)
        print("  refs <file> <line> <col>           - Find references", file=sys.stderr)
        print("  hover <file> <line> <col>          - Symbol information", file=sys.stderr)
        print("  rename <file> <line> <col> <name>  - Semantic rename", file=sys.stderr)
        print("  occurrences <file> <line> <col>    - Semantic occurrences", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    # Parse --root flag
    root = "."
    if "--root" in sys.argv:
        idx = sys.argv.index("--root")
        if idx + 1 < len(sys.argv):
            root = sys.argv[idx + 1]
            # Remove --root and its value from args
            sys.argv.pop(idx)  # Remove --root
            sys.argv.pop(idx)  # Remove value

    # Get remaining args (after command)
    args = sys.argv[2:]

    # Route command
    command_handlers = {
        "defs": handle_defs,
        "refs": handle_refs,
        "hover": handle_hover,
        "rename": handle_rename,
        "occurrences": handle_occurrences,
    }

    handler = command_handlers.get(command)
    if handler is None:
        print(f"Error: Unknown command '{command}'", file=sys.stderr)
        sys.exit(1)

    handler(args, root)


if __name__ == "__main__":
    main()
