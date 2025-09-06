import json
from pathlib import Path


def test_snapshot_creation(pytester, tmp_path: Path):
    # create a simple passing test
    pytester.makepyfile(
        test_sample="""
        def test_ok():
            assert 1 == 1
        """
    )

    out = tmp_path / "snap.json"
    # Run pytest with our plugin explicitly loaded
    result = pytester.runpytest(
        "-p",
        "pytest_snap.plugin",
        "--snap",
        "--snap-out",
        str(out),
    )
    result.assert_outcomes(passed=1)
    assert out.exists(), "snapshot JSON should be written"

    data = json.loads(out.read_text())
    assert "results" in data and isinstance(data["results"], list)
    assert any(r.get("outcome") == "passed" for r in data["results"])
