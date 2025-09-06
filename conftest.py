"""Top-level pytest configuration.

We intentionally avoid declaring pytest_plugins here unless a plugin is
strictly needed across the entire repository. The previous nested
`example_suite/tests/conftest.py` declared `pytest_plugins = ["pytester"]`
which is deprecated in non-top-level conftest files (Pytest 8 deprecation).

If tests require the `pytester` plugin, uncomment the line below.
"""

# Enable pytester fixture for internal tests only (not installed runtime).
pytest_plugins = ["pytester"]
