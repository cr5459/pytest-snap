from pytest_html_baseline.diff import diff_snapshots


def make_snap(tests):
    return {"version": 1, "created_at": "", "collected": len(tests), "tests": tests}


def test_new_and_vanished_failures():
    baseline = make_snap([
        {"id": "a::test_ok", "outcome": "passed", "duration": 0.1},
        {"id": "a::test_fail", "outcome": "failed", "duration": 0.2},
    ])
    current = make_snap([
        {"id": "a::test_ok", "outcome": "failed", "duration": 0.15},  # new failure
        {"id": "a::test_new", "outcome": "failed", "duration": 0.05},  # new test failure
    ])
    d = diff_snapshots(baseline, current, slower_ratio=1.3, slower_abs=0.2)
    ids_new = {r["id"] for r in d["new_failures"]}
    assert "a::test_ok" in ids_new and "a::test_new" in ids_new
    vanished_ids = {r["id"] for r in d["vanished_failures"]}
    assert "a::test_fail" in vanished_ids


def test_slower_detection_ratio_and_abs():
    baseline = make_snap([{"id": "t::slow", "outcome": "passed", "duration": 1.0}])
    current = make_snap([{"id": "t::slow", "outcome": "passed", "duration": 1.35}])
    d = diff_snapshots(baseline, current, slower_ratio=1.3, slower_abs=0.2)
    assert d["slower_tests"][0]["id"] == "t::slow"
    # Below thresholds
    current2 = make_snap([{"id": "t::slow", "outcome": "passed", "duration": 1.10}])
    d2 = diff_snapshots(baseline, current2, slower_ratio=1.3, slower_abs=0.2)
    assert not d2["slower_tests"]


def test_flaky_suspects():
    baseline = make_snap([{"id": "t::f", "outcome": "passed", "duration": 0.1}])
    current = make_snap([{"id": "t::f", "outcome": "failed", "duration": 0.2}])
    d = diff_snapshots(baseline, current, slower_ratio=2, slower_abs=5)
    assert d["flaky_suspects"][0]["id"] == "t::f"


def test_idempotence_empty_changes():
    snap = make_snap([{"id": "t::same", "outcome": "passed", "duration": 0.2}])
    d = diff_snapshots(snap, snap, slower_ratio=1.3, slower_abs=0.2)
    for k in ["new_failures", "vanished_failures", "flaky_suspects", "slower_tests"]:
        assert not d[k]
