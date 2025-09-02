from __future__ import annotations

from typing import Dict, Iterable, List, Any


def build_index(tests: Iterable[dict]) -> Dict[str, dict]:
    return {t["id"]: t for t in tests}


def diff_snapshots(
    baseline: dict | None,
    current: dict,
    *,
    slower_ratio: float,
    slower_abs: float,
) -> dict:
    b_index = build_index(baseline.get("tests", [])) if baseline else {}
    c_index = build_index(current.get("tests", []))

    new_failures = []
    vanished_failures = []
    flaky_suspects = []
    slower_tests = []

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
            new_failures.append({"id": cid, "from": bout, "to": cout})
        # Flaky suspect: toggled outcome pass/fail states (include xfail/xpass changes)
        if (bout != cout) and {bout, cout} & {"failed", "passed", "xfailed", "xpassed", "xfail", "xpass"}:
            flaky_suspects.append({"id": cid, "from": bout, "to": cout})
        # Slower test (need both durations)
        try:
            d0 = float(btest.get("duration", 0.0))
            d1 = float(ctest.get("duration", 0.0))
        except Exception:
            d0 = d1 = 0.0
        if d0 > 0 and d1 >= max(d0 * slower_ratio, d0 + slower_abs):
            ratio = (d1 / d0) if d0 else 0.0
            slower_tests.append({"id": cid, "prev": round(d0, 6), "curr": round(d1, 6), "ratio": round(ratio, 3)})

    for bid, btest in b_index.items():
        if bid not in c_index:
            # Vanished failure if it was failing
            if btest.get("outcome") == "failed":
                vanished_failures.append({"id": bid})
        else:
            bout = btest.get("outcome")
            cout = c_index[bid].get("outcome")
            if bout == "failed" and cout not in {"failed", "xfail"}:
                vanished_failures.append({"id": bid})

    summary = {
        "n_new": len(new_failures),
        "n_vanished": len(vanished_failures),
        "n_flaky": len(flaky_suspects),
        "n_slower": len(slower_tests),
    }
    return {
        "new_failures": new_failures,
        "vanished_failures": vanished_failures,
        "flaky_suspects": flaky_suspects,
        "slower_tests": slower_tests,
        "summary": summary,
    }
