# PyCLIDE Test Suite

This directory contains automated tests for PyCLIDE.

## Structure

```
tests/
├── __init__.py              # Test package initialization
├── README.md                # This file
├── fixtures/                # Test fixtures (sample Python files)
│   ├── sample_module.py     # Sample module with classes and functions
│   └── sample_usage.py      # Sample file that imports sample_module
├── test_jedi_features.py    # Tests for Jedi integration (goto, infer, refs, hover)
├── test_rope_features.py    # Tests for Rope integration (rename, occurrences, extract)
└── test_utilities.py        # Tests for utility functions
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test file
```bash
pytest tests/test_jedi_features.py
```

### Run specific test class
```bash
pytest tests/test_jedi_features.py::TestJediFeatures
```

### Run specific test
```bash
pytest tests/test_jedi_features.py::TestJediFeatures::test_jedi_goto_function_definition
```

### Run tests with markers
```bash
# Run only Jedi tests
pytest -m jedi

# Run only Rope tests
pytest -m rope

# Run only utility tests
pytest -m utility
```

### Run with verbose output
```bash
pytest -v
```

### Run with coverage (requires pytest-cov)
```bash
pytest --cov=pyclide --cov-report=html
```

## Test Categories

### Jedi Tests (`test_jedi_features.py`)
Tests for static analysis features powered by Jedi:
- `test_jedi_goto_*` - Tests for "go to definition" functionality
- `test_jedi_infer_*` - Tests for type inference
- `test_jedi_get_references` - Tests for finding references
- `test_jedi_hover_*` - Tests for hover information (docstrings, signatures)
- `test_jedi_complete` - Tests for code completion

### Rope Tests (`test_rope_features.py`)
Tests for refactoring features powered by Rope:
- `test_rope_occurrences_*` - Tests for finding semantic occurrences
- `test_rope_rename_*` - Tests for rename refactoring
- `test_rope_extract_*` - Tests for extract method/variable refactoring
- `test_rope_organize_imports` - Tests for import organization

### Utility Tests (`test_utilities.py`)
Tests for utility functions:
- `test_rel_to_*` - Tests for relative path calculation
- `test_byte_offset_*` - Tests for line/column to byte offset conversion
- `test_list_globals_*` - Tests for AST-based symbol listing
- `test_simple_text_search` - Tests for text-based search

## Fixtures

The `fixtures/` directory contains sample Python files used for testing:

- **sample_module.py**: A module with functions, classes, and docstrings
- **sample_usage.py**: A file that imports and uses sample_module

These fixtures are designed to test various PyCLIDE features in realistic scenarios.

## Requirements

To run the tests, you need:
- pytest
- jedi (for Jedi tests)
- rope (for Rope tests)

Install with:
```bash
pip install pytest jedi rope
```

Optional:
```bash
pip install pytest-cov  # For coverage reports
```

## Adding New Tests

When adding new tests:

1. Follow the existing naming conventions (`test_*.py`, `Test*` classes, `test_*` methods)
2. Add appropriate docstrings explaining what the test does
3. Use fixtures for shared setup code
4. Add markers if the test fits a category
5. Keep tests focused and independent

## Notes

- Tests use temporary directories when testing file modifications (Rope features)
- Fixtures are copied to temp directories to avoid modifying the originals
- Tests are designed to be fast and independent (no shared state between tests)
