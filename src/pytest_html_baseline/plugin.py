from __future__ import annotations

import json
from typing import List

import pytest

from .baseline import (
    TestRecord,
    failure_signature,
    write_snapshot,
    read_snapshot,
    append_history,
    load_history,
    compute_flake_scores,
    normalize_test_id,
)
from .diff import diff_snapshots
from .config import BaselineConfig
from .budgets import load_budgets, compute_budget_violations


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
    group.addoption(
        "--html-baseline-verbose",
        action="store_true",
        dest="html_baseline_verbose",
        help="Print baseline diff summary to console for debugging",
        default=False,
    )
    group.addoption(
        "--html-baseline-badges",
        action="store_true",
        dest="html_baseline_badges",
        help="Annotate pytest-html rows with baseline diff badges",
        default=False,
    )
    group.addoption(
        "--html-flake-threshold",
        action="store",
        dest="html_flake_threshold",
        type=float,
        default=0.15,
    )
    group.addoption(
        "--html-budgets",
        action="store",
        dest="html_budgets",
        help="YAML/JSON file containing performance budgets",
    )
    group.addoption(
        "--html-history-path",
        action="store",
        dest="html_history_path",
        help="Path for rolling history jsonl (set to 'off' to disable). Defaults to .artifacts/history.jsonl",
        default=None,
    )
    group.addoption(
        "--html-history-max",
        action="store",
        dest="html_history_max",
        type=int,
        help="Maximum retained history lines (default 20)",
        default=None,
    )


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):  # pragma: no cover - integration
    config._html_baseline_records: List[TestRecord] = []  # type: ignore[attr-defined]
    config._html_baseline_diff = None  # type: ignore[attr-defined]
    config._html_baseline_cfg = BaselineConfig.from_options(config)  # type: ignore[attr-defined]
    config._html_baseline_badges = getattr(config.option, "html_baseline_badges", False)


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
    # Normalize xfail/xpass outcomes so diff logic can classify explicitly.
    if hasattr(rep, "wasxfail"):
        # Pytest may report xfail internal outcome as 'failed' or 'skipped' depending on version/strictness.
        if rep.outcome in {"failed", "skipped"}:
            out = "xfailed"
        elif rep.outcome == "passed":
            out = "xpassed"
        else:
            out = rep.outcome
    else:
        out = rep.outcome
    longrepr = rep.longrepr if out == "failed" else None
    sig = failure_signature(longrepr)
    cfg = getattr(config, "_html_baseline_cfg", None)
    norm_mode = getattr(cfg, "normalization_mode", "off") if cfg else "off"
    norm_id = normalize_test_id(item.nodeid, norm_mode)
    rec = TestRecord(id=norm_id, outcome=out, duration=duration, sig=sig)
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
            if getattr(config.option, "html_baseline_verbose", False):
                print(f"[pytest-snap] Failed to write snapshot to {save_path}")

    # Append to history for flake score computation
    cfg = getattr(config, "_html_baseline_cfg", None)
    flake_scores = {}
    if cfg and cfg.history_path:
        history_path = cfg.history_path
        try:
            append_history(history_path, run_id=current.get("created_at", ""), records=records, max_lines=cfg.history_max)
        except Exception:
            pass
        history = load_history(history_path)
        flake_scores = compute_flake_scores(history)

    if baseline:
        cfg = getattr(config, "_html_baseline_cfg")
        # Respect minimum count noise gate
        if collected >= cfg.min_count:
            budgets_spec = load_budgets(getattr(config.option, "html_budgets", None))
            # gather durations per id for p95 if budgets present
            observed_durations = {}
            if budgets_spec:
                for t in current["tests"]:
                    observed_durations.setdefault(t["id"], []).append(t.get("duration", 0.0))
            budget_violations = []
            if budgets_spec:
                budget_violations = compute_budget_violations(budgets_spec, observed_durations)
            diff = diff_snapshots(
                baseline,
                current,
                slower_ratio=cfg.slower_ratio,
                slower_abs=cfg.slower_abs,
                flake_scores=flake_scores,
                flake_threshold=cfg.flake_threshold,
                min_count=cfg.min_count,
                budgets=budget_violations,
            )
            config._html_baseline_diff = diff  # type: ignore[attr-defined]
            diff_json_path = getattr(config.option, "html_diff_json", None)
            if diff_json_path:
                try:
                    with open(diff_json_path, "w", encoding="utf-8") as f:
                        json.dump(diff, f, separators=(",", ":"))
                except Exception:
                    pass
            # Always print a concise console summary to aid discoverability
            summ = diff["summary"]
            print(
                (
                    "[pytest-snap] new_failures={n_new} new_passes={n_new_passes} "
                    "new_xfails={n_new_xfails} resolved_xfails={n_resolved_xfails} persistent_xfails={n_persistent_xfails} "
                    "xpassed={n_xpassed} fixed={n_fixed} removed={n_removed} vanished(agg)={n_vanished} "
                    "flaky={n_flaky} slower={n_slower}"
                ).format(**summ)
            )
            if getattr(config.option, "html_baseline_verbose", False):
                # Show first few examples for debugging
                def head(lst, n=3):
                    return ", ".join(r.get("id", "?") for r in lst[:n]) or "-"

                print(
                    "[pytest-snap] examples: "
                    f"new:[{head(diff['new_failures'])}] vanished:[{head(diff['vanished_failures'])}] "
                    f"slower:[{head(diff['slower_tests'])}]"
                )
            fail_on = cfg.fail_on
            should_fail = False
            if fail_on == "new-failures" and diff and diff["summary"]["n_new"] > 0:
                should_fail = True
            elif fail_on == "slower" and diff and diff["summary"]["n_slower"] > 0:
                should_fail = True
            elif fail_on == "budgets" and diff and diff["summary"].get("n_budget", 0) > 0:
                should_fail = True
            elif fail_on == "any" and diff and any(
                diff["summary"].get(k, 0) > 0 for k in ["n_new", "n_slower", "n_flaky", "n_budget"]
            ):
                should_fail = True
            if should_fail:
                session.exitstatus = 1


# Optional: integrate rendering if pytest-html is present. The hook function is in render.py
try:  # pragma: no cover
    import pytest_html  # noqa: F401
    from . import render  # noqa: F401
except Exception:  # pragma: no cover
    pass
