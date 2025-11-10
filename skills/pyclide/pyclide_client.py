#!/usr/bin/env python3
"""
PyCLIDE Client - Single-file script for Claude Code skill.

Zero external dependencies (stdlib only).
Manages server lifecycle and routes commands to pyclide-server.
Also provides local-only features (list symbols, ast-grep codemod).

Server Commands (Jedi/Rope via pyclide-server):
    python pyclide_client.py defs app.py 10 5 --root .
    python pyclide_client.py rename app.py 10 5 new_name --root .

Local Commands (No server required):
    python pyclide_client.py list . --root .
    python pyclide_client.py codemod rule.yml --root . --apply
"""

import ast
import json
import shutil
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
            # Windows: Use cmd.exe with /c start /b to launch in background without window
            # This prevents CMD window from appearing when uvx runs
            CREATE_NO_WINDOW = 0x08000000
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "/b"] + cmd,
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
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


def handle_rename(args: List[str], root: str, output_format: str = "diff") -> None:
    """Handle 'rename' command (semantic rename)."""
    if len(args) < 4:
        print("Usage: pyclide_client.py rename <file> <line> <col> <new_name> [--root <root>] [--output-format <diff|full>]", file=sys.stderr)
        sys.exit(1)

    file_path, line, col, new_name = args[0], int(args[1]), int(args[2]), args[3]
    server_info = get_or_start_server(root)

    result = send_request(server_info, "rename", {
        "file": file_path,
        "line": line,
        "col": col,
        "new_name": new_name,
        "root": root,
        "output_format": output_format
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


def handle_extract_method(args: List[str], root: str, output_format: str = "diff") -> None:
    """Handle 'extract-method' command (extract code to method)."""
    if len(args) < 4:
        print("Usage: pyclide_client.py extract-method <file> <start_line> <end_line> <method_name> [--root <root>] [--output-format <diff|full>]", file=sys.stderr)
        sys.exit(1)

    file_path, start_line, end_line, method_name = args[0], int(args[1]), int(args[2]), args[3]
    server_info = get_or_start_server(root)

    result = send_request(server_info, "extract-method", {
        "file": file_path,
        "start_line": start_line,
        "end_line": end_line,
        "method_name": method_name,
        "root": root,
        "output_format": output_format
    })

    print(json.dumps(result, indent=2))


def handle_extract_var(args: List[str], root: str, output_format: str = "diff") -> None:
    """Handle 'extract-var' command (extract expression to variable)."""
    if len(args) < 4:
        print("Usage: pyclide_client.py extract-var <file> <start_line> <end_line> <var_name> [--start-col <col>] [--end-col <col>] [--root <root>] [--output-format <diff|full>]", file=sys.stderr)
        sys.exit(1)

    file_path, start_line, end_line, var_name = args[0], int(args[1]), int(args[2]), args[3]

    # Parse optional --start-col and --end-col
    start_col = None
    end_col = None
    if "--start-col" in sys.argv:
        idx = sys.argv.index("--start-col")
        if idx + 1 < len(sys.argv):
            start_col = int(sys.argv[idx + 1])
    if "--end-col" in sys.argv:
        idx = sys.argv.index("--end-col")
        if idx + 1 < len(sys.argv):
            end_col = int(sys.argv[idx + 1])

    server_info = get_or_start_server(root)

    request_data = {
        "file": file_path,
        "start_line": start_line,
        "end_line": end_line,
        "var_name": var_name,
        "root": root,
        "output_format": output_format
    }
    if start_col is not None:
        request_data["start_col"] = start_col
    if end_col is not None:
        request_data["end_col"] = end_col

    result = send_request(server_info, "extract-var", request_data)

    print(json.dumps(result, indent=2))


def handle_move(args: List[str], root: str, output_format: str = "diff") -> None:
    """Handle 'move' command (move symbol/module)."""
    if len(args) < 4:
        print("Usage: pyclide_client.py move <file> <line> <col> <dest_file> [--root <root>] [--output-format <diff|full>]", file=sys.stderr)
        sys.exit(1)

    file_path, line, col, dest_file = args[0], int(args[1]), int(args[2]), args[3]
    server_info = get_or_start_server(root)

    result = send_request(server_info, "move", {
        "file": file_path,
        "line": line,
        "col": col,
        "dest_file": dest_file,
        "root": root,
        "output_format": output_format
    })

    print(json.dumps(result, indent=2))


def handle_organize_imports(args: List[str], root: str, output_format: str = "diff") -> None:
    """Handle 'organize-imports' command (normalize imports)."""
    if len(args) < 1:
        print("Usage: pyclide_client.py organize-imports <file> [--root <root>] [--output-format <diff|full>]", file=sys.stderr)
        sys.exit(1)

    file_path = args[0]
    server_info = get_or_start_server(root)

    result = send_request(server_info, "organize-imports", {
        "file": file_path,
        "root": root,
        "output_format": output_format
    })

    print(json.dumps(result, indent=2))


# ============================================================================
# Local Commands (No Server Required)
# ============================================================================

def handle_list(args: List[str], root: str) -> None:
    """Handle 'list' command (list top-level symbols via AST parsing)."""
    if len(args) < 1:
        print("Usage: pyclide_client.py list <file_or_dir> [--root <root>]", file=sys.stderr)
        sys.exit(1)

    path_arg = args[0]
    rootp = Path(root).resolve()
    target = (rootp / path_arg).resolve()

    if not target.exists():
        print(f"Error: Path not found: {target}", file=sys.stderr)
        sys.exit(1)

    # Collect Python files
    files = [target] if target.is_file() else list(target.rglob("*.py"))

    symbols = []
    for file in files:
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except Exception:
            continue  # Skip files with syntax errors

        # Extract top-level classes and functions
        for node in tree.body:
            rel_path = str(file.relative_to(rootp)) if file.is_relative_to(rootp) else str(file)

            if isinstance(node, ast.ClassDef):
                symbols.append({
                    "path": rel_path,
                    "kind": "class",
                    "name": node.name,
                    "line": node.lineno
                })
            elif isinstance(node, ast.FunctionDef):
                symbols.append({
                    "path": rel_path,
                    "kind": "function",
                    "name": node.name,
                    "line": node.lineno
                })

    print(json.dumps(symbols, indent=2))


def handle_codemod(args: List[str], root: str) -> None:
    """Handle 'codemod' command (AST transformations via ast-grep)."""
    if len(args) < 1:
        print("Usage: pyclide_client.py codemod <rule.yml> [--root <root>] [--apply]", file=sys.stderr)
        sys.exit(1)

    rule_file = args[0]
    apply_changes = "--apply" in sys.argv

    # Check if ast-grep is available
    if not shutil.which("ast-grep"):
        print("Error: ast-grep not found in PATH", file=sys.stderr)
        print("Install with: npm install -g @ast-grep/cli", file=sys.stderr)
        print("or visit: https://ast-grep.github.io/", file=sys.stderr)
        sys.exit(1)

    rootp = Path(root).resolve()
    cmd = ["ast-grep", "-c", rule_file, str(rootp)]

    if apply_changes:
        cmd.append("--rewrite")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        # ast-grep returns 0 with matches, 2 with no matches - both are success
        if result.returncode not in (0, 2):
            print(f"Error: ast-grep failed with code {result.returncode}", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            sys.exit(result.returncode)

        # Output result as JSON
        output = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "applied": apply_changes
        }
        print(json.dumps(output, indent=2))

    except subprocess.TimeoutExpired:
        print("Error: ast-grep command timed out after 30 seconds", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error running ast-grep: {e}", file=sys.stderr)
        sys.exit(1)


# ============================================================================
# CLI Entry Point
# ============================================================================

def main() -> None:
    """Main entry point for pyclide_client."""
    if len(sys.argv) < 2:
        print("Usage: python pyclide_client.py <command> [args...] [--root <root>]", file=sys.stderr)
        print("\nNavigation Commands (Jedi):", file=sys.stderr)
        print("  defs <file> <line> <col>                           - Go to definition", file=sys.stderr)
        print("  refs <file> <line> <col>                           - Find references", file=sys.stderr)
        print("  hover <file> <line> <col>                          - Symbol information", file=sys.stderr)
        print("\nRefactoring Commands (Rope):", file=sys.stderr)
        print("  occurrences <file> <line> <col>                    - Semantic occurrences", file=sys.stderr)
        print("  rename <file> <line> <col> <new_name>              - Semantic rename", file=sys.stderr)
        print("  extract-method <file> <sl> <el> <name>             - Extract method", file=sys.stderr)
        print("  extract-var <file> <sl> <el> <name> [--start-col] [--end-col] - Extract variable", file=sys.stderr)
        print("  move <file> <line> <col> <dest_file>               - Move symbol/module", file=sys.stderr)
        print("  organize-imports <file>                            - Normalize imports", file=sys.stderr)
        print("\nLocal Commands (No Server):", file=sys.stderr)
        print("  list <file_or_dir>                                 - List symbols (AST)", file=sys.stderr)
        print("  codemod <rule.yml> [--apply]                       - AST transformations", file=sys.stderr)
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

    # Parse --output-format flag (default: "diff")
    output_format = "diff"
    if "--output-format" in sys.argv:
        idx = sys.argv.index("--output-format")
        if idx + 1 < len(sys.argv):
            output_format = sys.argv[idx + 1]
            if output_format not in ("diff", "full"):
                print(f"Error: --output-format must be 'diff' or 'full', got '{output_format}'", file=sys.stderr)
                sys.exit(1)
            # Remove --output-format and its value from args
            sys.argv.pop(idx)  # Remove --output-format
            sys.argv.pop(idx)  # Remove value

    # Get remaining args (after command)
    args = sys.argv[2:]

    # Route command
    command_handlers = {
        # Navigation commands (Jedi)
        "defs": handle_defs,
        "refs": handle_refs,
        "hover": handle_hover,
        # Refactoring commands (Rope)
        "occurrences": handle_occurrences,
        "rename": handle_rename,
        "extract-method": handle_extract_method,
        "extract-var": handle_extract_var,
        "move": handle_move,
        "organize-imports": handle_organize_imports,
        # Local commands (no server)
        "list": handle_list,
        "codemod": handle_codemod,
    }

    handler = command_handlers.get(command)
    if handler is None:
        print(f"Error: Unknown command '{command}'", file=sys.stderr)
        sys.exit(1)

    # Pass output_format to refactoring commands
    refactoring_commands = {"rename", "extract-method", "extract-var", "move", "organize-imports"}
    if command in refactoring_commands:
        handler(args, root, output_format)
    else:
        handler(args, root)


if __name__ == "__main__":
    main()
