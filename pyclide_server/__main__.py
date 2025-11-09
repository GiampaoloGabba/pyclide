"""
PyCLIDE Server entry point.

Usage:
    python -m pyclide_server --root /path/to/project --port 5001
    uvx pyclide-server --root /path/to/project --port 5001 --daemon
"""

import argparse
import sys
from pathlib import Path

from .server import PyCLIDEServer


def main():
    """Main entry point for pyclide-server."""
    parser = argparse.ArgumentParser(
        description="PyCLIDE Server - High-performance Python semantic analysis server"
    )
    parser.add_argument(
        "--root",
        type=str,
        required=True,
        help="Workspace root directory (project root)"
    )
    parser.add_argument(
        "--port",
        type=int,
        required=True,
        help="Port to bind the server to (typically 5000-6000)"
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run in daemon mode (background process)"
    )

    args = parser.parse_args()

    # Validate workspace root
    workspace_root = Path(args.root).resolve()
    if not workspace_root.exists():
        print(f"Error: Workspace root does not exist: {workspace_root}", file=sys.stderr)
        sys.exit(1)

    if not workspace_root.is_dir():
        print(f"Error: Workspace root is not a directory: {workspace_root}", file=sys.stderr)
        sys.exit(1)

    # Daemon mode: detach from terminal
    if args.daemon:
        if sys.platform == "win32":
            # On Windows, the client should handle process creation with DETACHED_PROCESS
            # Here we just ensure we don't block on stdin/stdout
            pass
        else:
            # On Unix, we could fork here, but the client handles start_new_session=True
            # So we just continue normally
            pass

    # Create and start server
    try:
        server = PyCLIDEServer(str(workspace_root), args.port)
        server.start()
    except KeyboardInterrupt:
        print("\nServer stopped by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Error starting server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
