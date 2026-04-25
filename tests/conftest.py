"""
tests/conftest.py

Shared pytest fixtures and configuration for the full test suite.

Fixtures defined here are available to all tests without explicit import.
Keep this file minimal — service-specific fixtures belong in their own
conftest.py files inside the relevant test subdirectory.
"""

import pytest


@pytest.fixture(scope="session")
def project_root(tmp_path_factory):
    """Return the project root path for tests that need to reference files."""
    import pathlib
    return pathlib.Path(__file__).parent.parent
