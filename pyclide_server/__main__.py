"""
PyCLIDE Server entry point.

Usage:
    python -m pyclide_server --root /path/to/project --port 5001
    uvx pyclide-server --root /path/to/project --port 5001 --daemon
"""

import argparse
import logging
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

    # Configure logging before importing server modules
    if args.daemon:
        # Setup logging to file for daemon mode
        log_dir = Path.home() / ".pyclide" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"server_{args.port}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(log_file)]
        )
    else:
        # Console logging for non-daemon mode
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

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
            # On Windows, detach from console to prevent CMD window
            try:
                import ctypes
                kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
                if kernel32.FreeConsole():
                    # Successfully detached from console
                    # Redirect stdout/stderr to null to avoid write errors
                    sys.stdout = open('nul', 'w')
                    sys.stderr = open('nul', 'w')
                    sys.stdin = open('nul', 'r')
            except Exception:
                # If FreeConsole fails, continue anyway (client might have used CREATE_NO_WINDOW)
                pass
        else:
            # On Unix, redirect streams to /dev/null
            try:
                sys.stdout = open('/dev/null', 'w')
                sys.stderr = open('/dev/null', 'w')
                sys.stdin = open('/dev/null', 'r')
            except Exception:
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
