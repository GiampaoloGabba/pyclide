"""
Jedi integration helpers.
Extracted from pyclide.py for server use.
"""

from typing import List, Dict, Any
from pathlib import Path
import jedi


def jedi_script(root: Path, file_path: str) -> jedi.Script:
    """
    Construct a Jedi Script for a given file.
    """
    path = str((root / file_path).resolve())
    return jedi.Script(path=path)


def jedi_to_locations(defs) -> List[Dict[str, Any]]:
    """
    Convert Jedi definitions/references to normalized location dicts.
    """
    out: List[Dict[str, Any]] = []
    for d in defs:
        if not getattr(d, "module_path", None) or getattr(d, "line", None) is None:
            continue
        out.append({
            "path": str(d.module_path),
            "line": d.line,
            "column": d.column or 1,
            "name": d.name,
            "type": d.type,
        })
    return out
