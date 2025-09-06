"""Top-level pytest configuration.

We intentionally avoid declaring pytest_plugins here unless a plugin is
strictly needed across the entire repository. Non-top-level conftest files
declaring plugins are deprecated in Pytest 8.

If tests require the `pytester` plugin, uncomment the line below.
"""

# Enable pytester fixture for internal tests only (not installed runtime).
pytest_plugins = ["pytester"]
