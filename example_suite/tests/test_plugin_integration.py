import json
import textwrap


def test_integration_baseline_and_diff(pytester):
    pytester.makepyfile(
        test_sample=textwrap.dedent(
            """
            import pytest

            def test_pass():
                pass

            def test_fail():
                assert 1 == 0
            """
        )
    )
    base = pytester.path / "base.json"
    # First run creates baseline
    r1 = pytester.runpytest(f"--html-save-baseline={base}")
    r1.assert_outcomes(passed=1, failed=1)
    assert base.exists()

    # Modify tests: failing test now passes, introduce new failing + slower
    pytester.makepyfile(
        test_sample=textwrap.dedent(
            """
            import time

            def test_pass():
                pass

            def test_fail():
                # was failing, now passes
                assert 1 == 1

            def test_new_fail():
                assert 2 == 1

            def test_slow():
                time.sleep(0.05)
            """
        )
    )
    diff_json = pytester.path / "diff.json"
    r2 = pytester.runpytest(
        f"--html-baseline={base}",
        f"--html-save-baseline={base}",
        f"--html-diff-json={diff_json}",
        "--html-fail-on=any",
        "--html-slower-threshold-ratio=1.3",
        "--html-slower-threshold-abs=0.001",
    )
    # Should fail due to new failure
    assert r2.ret != 0
    assert diff_json.exists()
    data = json.loads(diff_json.read_text())
    assert data["summary"]["n_new"] >= 1
    node_ids = {r['id'] for r in data['new_failures']}
    assert any(id.endswith('test_new_fail') for id in node_ids)
