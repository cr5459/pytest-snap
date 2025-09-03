from __future__ import annotations

from typing import Dict, Iterable, List, Any, Optional, Tuple

ImpactTuple = Tuple[int, str]  # (score, id)


def build_index(tests: Iterable[dict]) -> Dict[str, dict]:
    return {t["id"]: t for t in tests}


def diff_snapshots(
    baseline: dict | None,
    current: dict,
    *,
    slower_ratio: float,
    slower_abs: float,
    flake_scores: Optional[Dict[str, float]] = None,
    flake_threshold: float = 1.0,
    min_count: int = 0,
    budgets: Optional[List[dict]] = None,
) -> dict:
    b_index = build_index(baseline.get("tests", [])) if baseline else {}
    c_index = build_index(current.get("tests", []))

    new_failures = []
    new_passes = []      # brand new tests that are passing
    vanished_failures = []  # backward-compatible aggregate (fixed + removed)
    fixed_failures = []     # previously failed, now passed / not failing
    removed_failures = []   # previously failed test id no longer present
    new_xfails = []         # tests newly in an xfail state
    resolved_xfails = []    # tests that were xfail and now pass
    flaky_suspects = []
    slower_tests = []
    budget_violations = budgets or []

    # Iterate over union of ids efficiently
    for cid, ctest in c_index.items():
        btest = b_index.get(cid)
        cout = ctest.get("outcome")
        if btest is None:
            # New test; track failures and passes separately
            if cout == "failed":
                new_failures.append({"id": cid, "outcome": cout})
            elif cout == "passed":
                new_passes.append({"id": cid, "outcome": cout, "duration": ctest.get("duration")})
            elif cout in {"xfailed", "xfail"}:
                new_xfails.append({"id": cid, "outcome": cout})
            continue
        bout = btest.get("outcome")
        # New failure
        if cout == "failed" and bout not in {"failed", "xfail"}:
            new_failures.append({"id": cid, "from": bout, "to": cout, "sig": ctest.get("sig"), "duration": ctest.get("duration")})
        # Newly xfailed (baseline not xfail-like, current is xfail)
        if cout in {"xfailed", "xfail"} and bout not in {"xfailed", "xfail"}:
            new_xfails.append({"id": cid, "from": bout, "to": cout})
        # Resolved xfail (baseline xfail and now passing)
        if bout in {"xfailed", "xfail"} and cout == "passed":
            resolved_xfails.append({"id": cid, "from": bout, "to": cout})
        # Flaky suspect: toggled outcome pass/fail states (include xfail/xpass changes)
        if (bout != cout) and {bout, cout} & {"failed", "passed", "xfailed", "xpassed", "xfail", "xpass"}:
            fs = flake_scores.get(cid, 0.0) if flake_scores else 0.0
            flaky_suspects.append({"id": cid, "from": bout, "to": cout, "flake_score": round(fs, 4)})
        # Slower test (need both durations)
        try:
            d0 = float(btest.get("duration", 0.0))
            d1 = float(ctest.get("duration", 0.0))
        except Exception:
            d0 = d1 = 0.0
        if d0 > 0 and d1 >= max(d0 * slower_ratio, d0 + slower_abs):
            ratio = (d1 / d0) if d0 else 0.0
            slower_tests.append({"id": cid, "prev": round(d0, 6), "curr": round(d1, 6), "ratio": round(ratio, 3), "abs_delta": round(d1 - d0, 6)})

    for bid, btest in b_index.items():
        if bid not in c_index:
            # Removed test that used to fail
            if btest.get("outcome") == "failed":
                rec = {"id": bid, "sig": btest.get("sig")}
                vanished_failures.append(rec)
                removed_failures.append(rec)
        else:
            bout = btest.get("outcome")
            cout = c_index[bid].get("outcome")
            if bout == "failed" and cout not in {"failed", "xfail"}:
                rec = {"id": bid, "sig": btest.get("sig")}
                vanished_failures.append(rec)
                fixed_failures.append(rec)

    def _filter_flaky(bucket: List[dict]) -> List[dict]:
        if flake_scores is None or flake_threshold >= 1.0:
            return bucket
        out = []
        for r in bucket:
            fs = flake_scores.get(r["id"], 0.0)
            if fs < flake_threshold:
                out.append(r)
        return out

    new_failures_f = _filter_flaky(new_failures)
    slower_tests_f = _filter_flaky(slower_tests)
    budget_violations_f = _filter_flaky(budget_violations)

    summary = {
        "n_new": len(new_failures_f),
        "n_new_passes": len(new_passes),
        "n_vanished": len(vanished_failures),  # legacy aggregate
        "n_fixed": len(fixed_failures),
        "n_removed": len(removed_failures),
        "n_new_xfails": len(new_xfails),
        "n_resolved_xfails": len(resolved_xfails),
        "n_flaky": len(flaky_suspects),
        "n_slower": len(slower_tests_f),
        "n_budget": len(budget_violations_f),
    }
    # impact score (rough heuristic)
    impact = 3 * summary["n_new"] + 2 * summary["n_budget"] + summary["n_slower"]
    result = {
        "new_failures": new_failures_f[:50],
        "new_passes": new_passes[:50],
        "vanished_failures": vanished_failures[:50],  # union of fixed + removed
        "fixed_failures": fixed_failures[:50],
        "removed_failures": removed_failures[:50],
        "new_xfails": new_xfails[:50],
        "resolved_xfails": resolved_xfails[:50],
        "flaky_suspects": flaky_suspects[:50],
        "slower_tests": slower_tests_f[:50],
        "budget_violations": budget_violations_f[:50],
        "summary": summary,
        "impact_score": impact,
    }
    return result
