"""Minimal pytest-snap plugin.

This intentionally small implementation focuses on deterministic capture of
per-test outcomes + durations into a JSON snapshot. It is a foundation for
future perf / diff / gating features but keeps the initial surface area tiny.

Snapshot schema (0.1.0):
{
  "started_ns": <int>,
  "finished_ns": <int>,
  "env": {"pytest_version": "..."},
  "results": [
	 {"nodeid": "tests/test_x.py::test_foo", "outcome": "passed", "dur_ns": 123456}
  ]
}
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import os
import time
from typing import Dict, List

import pytest

__all__ = [
	"pytest_addoption",
]


@dataclass
class _SnapResult:
	nodeid: str
	outcome: str
	dur_ns: int


def pytest_addoption(parser: pytest.Parser) -> None:  # pragma: no cover - exercised via help test
	group = parser.getgroup("snap")
	group.addoption("--snap", action="store_true", help="Enable pytest-snap snapshotting")
	group.addoption(
		"--snap-out",
		action="store",
		default=".snap/current.json",
		help="Path to write current snapshot JSON (default: .snap/current.json)",
	)
	group.addoption(
		"--snap-baseline",
		action="store",
		default=None,
		help="(Reserved) baseline snapshot JSON to compare against (not yet used)",
	)
	group.addoption(
		"--snap-fail-on",
		action="store",
		default=None,
		help="(Reserved) gating policy (e.g. 'slower'). No effect in 0.1.0",
	)


def _enabled(config: pytest.Config) -> bool:
	return bool(config.getoption("--snap"))


def pytest_configure(config: pytest.Config) -> None:  # pragma: no cover - thin
	# Avoid double-registration if plugin loaded twice under different entry point names.
	if getattr(config, "_snap_initialized", False):  # type: ignore[attr-defined]
		return
	if not _enabled(config):
		return
	config._snap_initialized = True  # type: ignore[attr-defined]
	config._snap_started_ns = time.monotonic_ns()  # type: ignore[attr-defined]
	config._snap_results: List[Dict[str, object]] = []  # type: ignore[attr-defined]
	config.addinivalue_line("markers", "snap: mark test considered by pytest-snap (currently implicit)")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):  # pragma: no cover - thin wrapper
	outcome = yield
	rep: pytest.TestReport = outcome.get_result()  # type: ignore[assignment]
	if rep.when != "call" or not _enabled(item.config):
		return
	dur_ns = int(rep.duration * 1e9)
	results: List[Dict[str, object]] = item.config._snap_results  # type: ignore[attr-defined]
	results.append(asdict(_SnapResult(nodeid=rep.nodeid, outcome=rep.outcome, dur_ns=dur_ns)))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:  # pragma: no cover - integration semantics
	config = session.config
	if not _enabled(config):
		return
	snap_path = config.getoption("--snap-out")
	data = {
		"started_ns": getattr(config, "_snap_started_ns", None),
		"finished_ns": time.monotonic_ns(),
		"env": {"pytest_version": pytest.__version__},
		"results": getattr(config, "_snap_results", []),
	}
	os.makedirs(os.path.dirname(snap_path) or ".", exist_ok=True)
	with open(snap_path, "w", encoding="utf-8") as f:
		json.dump(data, f, indent=2)
