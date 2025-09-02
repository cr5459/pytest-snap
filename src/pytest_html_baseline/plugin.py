from __future__ import annotations

import json
from typing import List

import pytest

from .baseline import TestRecord, failure_signature, write_snapshot, read_snapshot
from .diff import diff_snapshots
from .config import BaselineConfig


COLLECTED_KEY = "_html_baseline_collected"


def pytest_addoption(parser):  # pragma: no cover - exercised via integration
    group = parser.getgroup("html-baseline")
    group.addoption("--html-save-baseline", action="store", dest="html_save_baseline")
    group.addoption("--html-baseline", action="store", dest="html_baseline")
    group.addoption(
        "--html-slower-threshold-ratio", action="store", dest="html_slower_threshold_ratio", type=float, default=1.30
    )
    group.addoption(
        "--html-slower-threshold-abs", action="store", dest="html_slower_threshold_abs", type=float, default=0.20
    )
    group.addoption("--html-min-count", action="store", dest="html_min_count", type=int, default=0)
    group.addoption(
        "--html-fail-on",
        action="store",
        dest="html_fail_on",
        choices=["new-failures", "slower", "any"],
        default="new-failures",
    )
    group.addoption("--html-diff-json", action="store", dest="html_diff_json")


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):  # pragma: no cover - integration
    config._html_baseline_records: List[TestRecord] = []  # type: ignore[attr-defined]
    config._html_baseline_diff = None  # type: ignore[attr-defined]
    config._html_baseline_cfg = BaselineConfig.from_options(config)  # type: ignore[attr-defined]


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):  # pragma: no cover - integration
    session.config._html_baseline_collected = 0  # type: ignore[attr-defined]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):  # pragma: no cover - integration
    outcome = yield
    # item execution done


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):  # pragma: no cover - integration
    outcome = yield
    rep = outcome.get_result()
    if rep.when != "call":
        return
    config = item.config
    duration = getattr(rep, "duration", 0.0)
    out = rep.outcome
    longrepr = rep.longrepr if out == "failed" else None
    sig = failure_signature(longrepr)
    rec = TestRecord(id=item.nodeid, outcome=out, duration=duration, sig=sig)
    config._html_baseline_records.append(rec)  # type: ignore[attr-defined]


def _load_snapshot(path: str | None):
    if not path:
        return None
    try:
        return read_snapshot(path)
    except FileNotFoundError:
        return None
    except Exception:
        return None


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):  # pragma: no cover - integration
    config = session.config
    records = getattr(config, "_html_baseline_records", [])
    collected = session.testscollected if hasattr(session, "testscollected") else len(records)
    # Load baseline BEFORE possibly overwriting it with --html-save-baseline
    baseline_path = getattr(config.option, "html_baseline", None)
    baseline = _load_snapshot(baseline_path)

    current = {"version": 1, "created_at": "", "collected": collected, "tests": [r.to_json() for r in records]}

    save_path = getattr(config.option, "html_save_baseline", None)
    if save_path:
        try:
            write_snapshot(save_path, records, collected)
        except Exception:
            pass

    if baseline:
        cfg = getattr(config, "_html_baseline_cfg")
        # Respect minimum count noise gate
        if collected >= cfg.min_count:
            diff = diff_snapshots(baseline, current, slower_ratio=cfg.slower_ratio, slower_abs=cfg.slower_abs)
            config._html_baseline_diff = diff  # type: ignore[attr-defined]
            diff_json_path = getattr(config.option, "html_diff_json", None)
            if diff_json_path:
                try:
                    with open(diff_json_path, "w", encoding="utf-8") as f:
                        json.dump(diff, f, separators=(",", ":"))
                except Exception:
                    pass
            fail_on = cfg.fail_on
            should_fail = False
            if fail_on == "new-failures" and diff["summary"]["n_new"] > 0:
                should_fail = True
            elif fail_on == "slower" and diff["summary"]["n_slower"] > 0:
                should_fail = True
            elif fail_on == "any" and any(diff["summary"][k] > 0 for k in ["n_new", "n_slower", "n_flaky"]):
                should_fail = True
            if should_fail:
                session.exitstatus = 1


# Optional: integrate rendering if pytest-html is present. The hook function is in render.py
try:  # pragma: no cover
    import pytest_html  # noqa: F401
    from . import render  # noqa: F401
except Exception:  # pragma: no cover
    pass
