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
    vanished_failures = []
    flaky_suspects = []
    slower_tests = []
    budget_violations = budgets or []

    # Iterate over union of ids efficiently
    for cid, ctest in c_index.items():
        btest = b_index.get(cid)
        cout = ctest.get("outcome")
        if btest is None:
            # New test; only matters if it's a new failure
            if cout == "failed":
                new_failures.append({"id": cid, "outcome": cout})
            continue
        bout = btest.get("outcome")
        # New failure
        if cout == "failed" and bout not in {"failed", "xfail"}:
            new_failures.append({"id": cid, "from": bout, "to": cout, "sig": ctest.get("sig"), "duration": ctest.get("duration")})
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
            # Vanished failure if it was failing
            if btest.get("outcome") == "failed":
                vanished_failures.append({"id": bid, "sig": btest.get("sig")})
        else:
            bout = btest.get("outcome")
            cout = c_index[bid].get("outcome")
            if bout == "failed" and cout not in {"failed", "xfail"}:
                vanished_failures.append({"id": bid, "sig": btest.get("sig")})

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
        "n_vanished": len(vanished_failures),
        "n_flaky": len(flaky_suspects),
        "n_slower": len(slower_tests_f),
        "n_budget": len(budget_violations_f),
    }
    # impact score (rough heuristic)
    impact = 3 * summary["n_new"] + 2 * summary["n_budget"] + summary["n_slower"]
    result = {
        "new_failures": new_failures_f[:50],
        "vanished_failures": vanished_failures[:50],
        "flaky_suspects": flaky_suspects[:50],
        "slower_tests": slower_tests_f[:50],
        "budget_violations": budget_violations_f[:50],
        "summary": summary,
        "impact_score": impact,
    }
    return result
