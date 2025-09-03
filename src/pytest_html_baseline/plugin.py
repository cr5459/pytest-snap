from __future__ import annotations

import warnings
from pytest_snap.plugin import *  # type: ignore  # noqa: F401,F403

warnings.warn(
    "Importing plugin from 'pytest_html_baseline' is deprecated; use 'pytest_snap' instead.",
    DeprecationWarning,
    stacklevel=2,
)
