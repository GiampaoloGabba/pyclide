#!/usr/bin/env bash
#
# PyCLIDE Wrapper Script
# Automatically selects the correct platform-specific binary and forwards all arguments.
#

set -e

# Determine the script directory (where this wrapper is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Determine plugin root (parent of scripts/)
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$SCRIPT_DIR")}"

# Detect platform
OS="$(uname -s)"
case "$OS" in
    Linux*)
        BINARY="$PLUGIN_ROOT/bin/pyclide-linux"
        ;;
    Darwin*)
        BINARY="$PLUGIN_ROOT/bin/pyclide-macos"
        ;;
    CYGWIN*|MINGW*|MSYS*|Windows*)
        BINARY="$PLUGIN_ROOT/bin/pyclide.exe"
        ;;
    *)
        echo "Error: Unsupported operating system: $OS" >&2
        exit 1
        ;;
esac

# Check if binary exists
if [[ ! -f "$BINARY" ]]; then
    echo "Error: PyCLIDE binary not found: $BINARY" >&2
    echo "Please build the binaries using: $PLUGIN_ROOT/build/build.sh" >&2
    exit 1
fi

# Make binary executable (in case permissions were lost)
chmod +x "$BINARY" 2>/dev/null || true

# Execute binary with all arguments forwarded
exec "$BINARY" "$@"
