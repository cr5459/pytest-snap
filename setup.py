from __future__ import annotations

"""Legacy setup.py.

This project is PEP 621 / pyproject.toml native. The setup.py exists only for
legacy tooling expectations (some environments still invoke `python setup.py`).
It dynamically reads metadata from pyproject.toml to avoid duplication.
"""

import pathlib
import sys

try:  # Python 3.11+
    import tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except Exception:
        print("tomllib/tomli unavailable; aborting setup", file=sys.stderr)
        raise

from setuptools import setup, find_packages

root = pathlib.Path(__file__).parent
data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
proj = data.get("project", {})
readme = proj.get("readme", {})
readme_file = readme.get("file")
long_description = ""
long_description_content_type: str | None = None
if readme_file and (root / readme_file).is_file():
    long_description = (root / readme_file).read_text(encoding="utf-8")
    long_description_content_type = readme.get("content-type")

license_field = proj.get("license")
if isinstance(license_field, str):
    license_str = license_field
elif isinstance(license_field, dict):
    license_str = license_field.get("text", "")
else:
    license_str = ""

setup(
    name=proj.get("name"),
    version=proj.get("version"),
    description=proj.get("description"),
    long_description=long_description,
    long_description_content_type=long_description_content_type or "text/markdown",
    python_requires=proj.get("requires-python"),
    license=license_str,
    packages=find_packages(),
    include_package_data=True,
    install_requires=proj.get("dependencies", []),
    classifiers=proj.get("classifiers", []),
)
