# PyCLIDE Plugin for Claude Code

**Python Command-Line IDE** packaged as a Claude Code skill with standalone executables.

Provides IDE-quality semantic code analysis and refactoring for Python projects using Jedi (navigation) and Rope (refactoring), without requiring Python dependencies in your project environment.

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

### Utilities
- **List symbols** - Quick overview of classes/functions (AST-based, fast)
- **AST codemods** - Mass transformations with ast-grep

**Note:** For text search, use Claude Code's native Grep tool (built-in ripgrep integration).

## Installation

### Option 1: Install to Personal Skills (Recommended)

Copy the plugin to your personal Claude Code skills directory:

```bash
# Linux/macOS
cp -r pyclide-plugin ~/.claude/skills/pyclide

# Windows (PowerShell)
Copy-Item -Recurse pyclide-plugin "$env:USERPROFILE\.claude\skills\pyclide"
```

### Option 2: Install to Project Skills

Copy to your project's `.claude/skills/` directory for team sharing:

```bash
cp -r pyclide-plugin /path/to/your-project/.claude/skills/pyclide
```

Then commit `.claude/skills/pyclide` to git (but see [.gitignore setup](#gitignore-for-binaries) for large binaries).

## Building Binaries

The plugin includes **standalone executables** to avoid polluting your project's Python environment with dependencies.

### Prerequisites

Install PyInstaller and dependencies:

```bash
pip install pyinstaller typer[all] jedi rope
```

### Build for Your Platform

**Linux/macOS:**
```bash
chmod +x build/build.sh
./build/build.sh
```

**Windows:**
```cmd
build\build.bat
```

This creates:
- `bin/pyclide.exe` (Windows)
- `bin/pyclide-linux` (Linux)
- `bin/pyclide-macos` (macOS)

### Cross-Platform Builds

To build for all platforms, run the build script on each OS:
1. Run `build.sh` on Linux → produces `bin/pyclide-linux`
2. Run `build.sh` on macOS → produces `bin/pyclide-macos`
3. Run `build.bat` on Windows → produces `bin/pyclide.exe`

Copy all binaries to `bin/` directory for full cross-platform support.

## Usage

Once installed, Claude Code will **automatically invoke** the skill when you request Python code analysis or refactoring.

### Example Prompts

- "Find all references to the `calculate_tax` function"
- "Rename `old_name` to `new_name` in utils.py line 42"
- "Extract lines 50-60 in app.py into a new method called `validate_input`"
- "Move the `User` class from models.py to user/models.py"
- "Show me what `process_payment` does at line 100"

### Manual Invocation

You can also invoke commands directly:

```bash
# Via wrapper script (auto-detects platform)
./scripts/pyclide-wrapper.sh defs app.py 10 5 --root .

# Or directly (platform-specific)
./bin/pyclide-linux defs app.py 10 5 --root .
```

## Documentation

- **[SKILL.md](skills/pyclide/SKILL.md)** - Concise skill reference for Claude
- **[REFERENCE.md](skills/pyclide/REFERENCE.md)** - Complete command documentation

## Optional Tools

PyCLIDE works out-of-the-box. The following optional tool enhances functionality:

### ast-grep (AST Transformations)

**All platforms:**
```bash
cargo install ast-grep
```

Or download from [ast-grep releases](https://github.com/ast-grep/ast-grep/releases)

## Project Structure

```
python-semantic-ide/
├── pyclide.py                   # 🔥 Main source code (CURRENT)
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest
├── skills/
│   └── pyclide/
│       ├── SKILL.md             # Skill definition (for Claude)
│       └── REFERENCE.md         # Complete command reference
├── bin/                         # Standalone executables
│   ├── pyclide.exe              # Windows binary
│   ├── pyclide-linux            # Linux binary
│   └── pyclide-macos            # macOS binary
├── scripts/
│   ├── pyclide-wrapper.sh       # Bash wrapper (Linux/macOS/Git Bash)
│   └── pyclide-wrapper.bat      # Batch wrapper (Windows)
├── build/
│   ├── build.sh                 # Build script (Linux/macOS)
│   └── build.bat                # Build script (Windows)
├── .gitignore                   # Ignore binaries and build artifacts
└── README.md                    # This file
```

## gitignore for Binaries

Since standalone binaries are large (~40-60 MB each), you may want to exclude them from git:

**Add to `.gitignore`:**
```gitignore
# PyCLIDE binaries (too large for git)
bin/pyclide*
!bin/.gitkeep

# Build artifacts
build/work/
build/*.spec
```

Users who clone the repo can build their own binaries using `build.sh` or `build.bat`.

**Alternative:** Use Git LFS (Large File Storage) if you want to commit binaries:
```bash
git lfs track "bin/pyclide*"
```

## Distribution

### As a Plugin Archive

1. Build binaries for all platforms
2. Create archive:
   ```bash
   tar -czf pyclide-plugin.tar.gz pyclide-plugin/
   # Or zip for Windows
   zip -r pyclide-plugin.zip pyclide-plugin/
   ```
3. Share the archive (users extract to `.claude/skills/`)

### Via Git Repository

1. Push to GitHub/GitLab
2. Users clone:
   ```bash
   cd ~/.claude/skills
   git clone https://github.com/yourusername/pyclide-plugin.git pyclide
   cd pyclide
   ./build/build.sh  # Build for their platform
   ```

### Via Claude Plugin Marketplace (Future)

Once Claude Code supports a plugin marketplace, this plugin can be published for one-click installation.

## Known Limitations

### Rope Refactoring Limitations

Rope is a powerful refactoring library, but has some limitations in complex scenarios:

**Cross-Directory References:**
- May not find all references when code uses `sys.path.insert()` or complex import mechanisms
- Works best with standard Python package structures (`__init__.py`, relative imports)

**Coordinate Precision:**
- Refactoring operations (rename, extract) require exact positioning on the identifier
- Position must point to the symbol name, not docstrings, comments, or whitespace
- Rope uses 1-based line numbers and 1-based column positions (byte offsets)

**Dynamic Code:**
- May not detect references in dynamically imported modules
- String-based imports (`__import__()`, `importlib`) are not tracked

**Recommendations:**
- For simple refactorings (rename, extract): Works reliably in standard codebases
- For complex multi-layer architectures: Verify changes before applying
- Use `--json` mode to preview changes before applying them
- Consider running tests after refactoring to catch edge cases

### Jedi Navigation Notes

- Jedi uses 1-based line numbers but 0-indexed column positions
- `goto` may return import locations instead of original definitions
- Works best with properly structured Python packages

## Troubleshooting

### "PyCLIDE binary not found"

Run the build script for your platform:
```bash
./build/build.sh    # Linux/macOS
build\build.bat     # Windows
```

### "Permission denied" (Linux/macOS)

Make wrapper and build scripts executable:
```bash
chmod +x scripts/pyclide-wrapper.sh
chmod +x build/build.sh
```

### "Jedi not installed" (when running source)

This message should never appear when using the standalone binary (it includes all dependencies). If you see it:
1. Verify you're using the binary, not the Python script directly
2. Rebuild the binary: `./build/build.sh`

### Build fails with "ModuleNotFoundError"

Install missing dependencies:
```bash
pip install pyinstaller typer[all] jedi rope
```

### Binary size is too large

Standalone binaries include Python runtime + all dependencies (~40-60 MB). This is expected and ensures zero dependency installation.

To reduce size:
- Use UPX compression (advanced): `pyinstaller --upx-dir=/path/to/upx ...`
- Or distribute source + require users to install Python dependencies

## Development

### Running from Source

For development, you can run the source directly (requires Python + dependencies):

```bash
# Install dependencies
pip install typer[all] jedi rope

# Run directly from root directory
python pyclide.py defs app.py 10 5 --root .
```

### Making Changes

1. Edit `pyclide.py` **(in the root directory)**
2. Test locally:
   ```bash
   python pyclide.py --help
   python pyclide.py defs test.py 1 1
   ```
3. Rebuild binaries:
   ```bash
   ./build/build.sh
   ```
4. Update version in:
   - `pyclide.py` (`VERSION = "x.y.z"`) - **root directory file**
   - `.claude-plugin/plugin.json` (`version`)

## License

MIT License - see source file for details.

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test on your platform
4. Submit a pull request

## Credits

- **Jedi** - Static analysis and code completion
- **Rope** - Python refactoring library
- **Typer** - Modern CLI framework
- **PyInstaller** - Python to executable bundler

## Support

- Issues: https://github.com/yourusername/pyclide-plugin/issues
- Documentation: See `skills/pyclide/REFERENCE.md`

---

**Built for Claude Code** | Designed for AI-assisted Python development
