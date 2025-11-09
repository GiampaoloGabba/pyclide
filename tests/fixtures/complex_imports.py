"""File with various import styles for testing import organization."""

# Standard library imports
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional

# Third party imports (if available)
import json

# Relative imports
from sample_module import Calculator, hello_world
from sample_module import calculate_sum

# Star import
from sample_usage import *

# Aliased imports
import os as operating_system
from pathlib import Path as FilePath


def use_imports():
    """Function that uses the imports to prevent unused import warnings."""
    # Use os
    current_dir = os.getcwd()

    # Use sys
    version = sys.version

    # Use Path
    p = Path(".")

    # Use typing
    my_list: List[str] = []
    my_dict: Dict[str, int] = {}
    optional_val: Optional[str] = None

    # Use json
    data = json.dumps({"key": "value"})

    # Use Calculator
    calc = Calculator(10)

    # Use hello_world
    greeting = hello_world("Test")

    # Use calculate_sum
    total = calculate_sum(1, 2)

    # Use aliased imports
    dir2 = operating_system.listdir(".")
    fp = FilePath("/tmp")

    return current_dir, version, p, my_list, my_dict, optional_val, data, calc, greeting, total, dir2, fp
