from hypothesis import given, strategies as st
from pytest_html_baseline.diff import diff_snapshots


TEST_ID = st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=["Ll", "Lu"], whitelist_characters=[":", "_"], min_codepoint=32, max_codepoint=126)).filter(lambda s: s.strip() != "")
OUTCOME = st.sampled_from(["passed", "failed", "skipped"])


def snap_strategy():
    def build(items):
        tests = []
        for i, (tid, outcome, dur) in enumerate(items):
            tests.append({"id": tid + str(i), "outcome": outcome, "duration": dur})
        return {"version": 1, "created_at": "", "collected": len(tests), "tests": tests}

    return st.lists(st.tuples(TEST_ID, OUTCOME, st.floats(0, 2)), max_size=40).map(build)


@given(snap_strategy())
def test_idempotence(snapshot):
    d = diff_snapshots(snapshot, snapshot, slower_ratio=1.3, slower_abs=0.2)
    assert all(len(d[k]) == 0 for k in ["new_failures", "vanished_failures", "flaky_suspects", "slower_tests"])


@given(snap_strategy(), snap_strategy(), st.floats(1.1, 2.0), st.floats(0.05, 0.5))
def test_monotonicity(baseline, current, ratio, abs_thr):
    d1 = diff_snapshots(baseline, current, slower_ratio=ratio, slower_abs=abs_thr)
    d2 = diff_snapshots(baseline, current, slower_ratio=ratio * 0.9, slower_abs=abs_thr * 0.9)
    # Tightening thresholds (lower ratio and abs) can only increase or keep slower tests
    assert len(d2["slower_tests"]) >= len(d1["slower_tests"])


@given(snap_strategy(), snap_strategy())
def test_partition_and_uniqueness(baseline, current):
    d = diff_snapshots(baseline, current, slower_ratio=1.3, slower_abs=0.2)
    union_ids = {t["id"] for t in baseline["tests"]} | {t["id"] for t in current["tests"]}
    new_ids = {r["id"] for r in d["new_failures"]}
    vanished_ids = {r["id"] for r in d["vanished_failures"]}
    # No duplicates inside buckets
    assert len(new_ids) == len(d["new_failures"]) and len(vanished_ids) == len(d["vanished_failures"])  # uniqueness
    # Buckets disjoint
    assert new_ids.isdisjoint(vanished_ids)
    # Every id classified either as new, vanished, or other (unchanged/changed not flagged)
    assert union_ids == (new_ids | vanished_ids | (union_ids - new_ids - vanished_ids))
