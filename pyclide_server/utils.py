"""
Shared utility functions for PyCLIDE server.
"""

import pathlib


def byte_offset(text: str, line_1based: int, col_1based: int) -> int:
    """
    Convert 1-based (line, col) to a 0-based byte offset for Rope.

    Rope APIs use a single offset in the file buffer; many agent UIs use line/col.

    Args:
        text: Source code text
        line_1based: 1-based line number
        col_1based: 1-based column number

    Returns:
        0-based byte offset in text
    """
    lines = text.splitlines(True)
    return sum(len(l) for l in lines[:max(0, line_1based - 1)]) + max(0, col_1based - 1)


def rel_to(root: pathlib.Path, path: pathlib.Path) -> str:
    """
    Return a path relative to root if possible, else the absolute path as string.

    Args:
        root: Root directory
        path: Path to make relative

    Returns:
        Relative path string or absolute path string
    """
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)
