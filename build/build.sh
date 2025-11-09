#!/usr/bin/env bash
#
# PyCLIDE Build Script
# Creates standalone executable using PyInstaller
#

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║           PyCLIDE Standalone Binary Builder             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
BIN_DIR="$PROJECT_ROOT/bin"

# Detect platform
OS="$(uname -s)"
case "$OS" in
    Linux*)
        PLATFORM="linux"
        OUTPUT_NAME="pyclide-linux"
        ;;
    Darwin*)
        PLATFORM="macos"
        OUTPUT_NAME="pyclide-macos"
        ;;
    CYGWIN*|MINGW*|MSYS*)
        PLATFORM="windows"
        OUTPUT_NAME="pyclide.exe"
        ;;
    *)
        echo "Error: Unsupported operating system: $OS"
        exit 1
        ;;
esac

echo "Platform detected: $PLATFORM"
echo "Output binary: $OUTPUT_NAME"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3.8+."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Check dependencies
echo ""
echo "Checking dependencies..."

MISSING_DEPS=()

python3 -c "import typer" 2>/dev/null || MISSING_DEPS+=("typer[all]")
python3 -c "import jedi" 2>/dev/null || MISSING_DEPS+=("jedi")
python3 -c "import rope" 2>/dev/null || MISSING_DEPS+=("rope")
python3 -c "import PyInstaller" 2>/dev/null || MISSING_DEPS+=("pyinstaller")

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo "Missing dependencies: ${MISSING_DEPS[*]}"
    echo ""
    echo "Install with:"
    echo "  pip install ${MISSING_DEPS[*]}"
    exit 1
fi

echo "✓ All dependencies installed"
echo ""

# Create bin directory if it doesn't exist
mkdir -p "$BIN_DIR"

# Build with PyInstaller
echo "Building standalone binary..."
echo ""

cd "$SCRIPTS_DIR"

pyinstaller \
    --onefile \
    --name "$OUTPUT_NAME" \
    --distpath "$BIN_DIR" \
    --workpath "$PROJECT_ROOT/build/work" \
    --specpath "$PROJECT_ROOT/build" \
    --clean \
    pyclide.py

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                   Build Successful!                      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Binary location: $BIN_DIR/$OUTPUT_NAME"
echo ""

# Get binary size
if [ -f "$BIN_DIR/$OUTPUT_NAME" ]; then
    SIZE=$(du -h "$BIN_DIR/$OUTPUT_NAME" | cut -f1)
    echo "Binary size: $SIZE"
    echo ""
fi

echo "Test the binary:"
echo "  $BIN_DIR/$OUTPUT_NAME --version"
echo ""

# Cross-platform build instructions
if [ "$PLATFORM" != "windows" ]; then
    echo "Note: To build for Windows, run this script on a Windows machine."
fi
if [ "$PLATFORM" != "linux" ]; then
    echo "Note: To build for Linux, run this script on a Linux machine."
fi
if [ "$PLATFORM" != "macos" ]; then
    echo "Note: To build for macOS, run this script on a macOS machine."
fi

echo ""
echo "After building for all platforms, you can distribute the plugin with:"
echo "  - bin/pyclide.exe (Windows)"
echo "  - bin/pyclide-linux (Linux)"
echo "  - bin/pyclide-macos (macOS)"
