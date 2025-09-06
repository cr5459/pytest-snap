from __future__ import annotations

import json, os


def test_snap_option_shows_in_help(pytester):
    result = pytester.runpytest('-p', 'pytest_snap.plugin', '-h')
    result.stdout.fnmatch_lines(['*--snap*Enable pytest-snap snapshotting*'])


def test_snapshot_file_schema(pytester):
    testfile = pytester.makepyfile("""
        def test_example():
            assert 1 + 1 == 2
    """)
    snap_path = os.path.join(str(pytester.path), 'out.json')
    result = pytester.runpytest('-p', 'pytest_snap.plugin', str(testfile), '--snap', '--snap-out', snap_path)
    result.assert_outcomes(passed=1)
    assert os.path.exists(snap_path)
    data = json.load(open(snap_path, 'r', encoding='utf-8'))
    assert 'started_ns' in data and isinstance(data['started_ns'], int)
    assert 'finished_ns' in data and isinstance(data['finished_ns'], int)
    assert data['finished_ns'] >= data['started_ns']
    assert 'env' in data and 'pytest_version' in data['env']
    assert isinstance(data.get('results'), list) and data['results']
    rec = data['results'][0]
    assert set(rec.keys()) == {'nodeid', 'outcome', 'dur_ns'}
    assert rec['outcome'] == 'passed'
    assert isinstance(rec['dur_ns'], int) and rec['dur_ns'] >= 0
