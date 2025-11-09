"""Pytest configuration and shared fixtures."""

import pytest


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "jedi: Tests for Jedi integration features")
    config.addinivalue_line("markers", "rope: Tests for Rope refactoring features")
    config.addinivalue_line("markers", "utility: Tests for utility functions")
    config.addinivalue_line("markers", "slow: Tests that take longer to run")
    config.addinivalue_line(
        "markers", "integration: Integration tests that test multiple components"
    )
