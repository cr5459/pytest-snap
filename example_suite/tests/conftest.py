"""Deprecated nested conftest retained intentionally empty.

Previously declared `pytest_plugins = ["pytester"]` here, which is no longer
allowed in non-top-level conftest files (Pytest deprecation). All repository
wide plugins should be declared in the root `conftest.py`.
"""

# (intentionally left blank)

