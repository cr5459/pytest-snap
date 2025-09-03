# pytest-html-baseline

Baseline comparison addon for pytest + optional pytest-html: detect new failures, vanished failures, flaky suspects, performance regressions, and performance budget violations between test runs. Produces an HTML panel (when pytest-html is installed) and machine-readable JSON for CI gating and automation.

## Features
- Capture a snapshot (baseline) of test outcomes & durations (plus failure fingerprints).
- O(n) diff of subsequent runs: new failures, vanished failures, flaky suspects, slower tests (ratio + abs), budget violations.
- Flake score computation from rolling history (jsonl) with threshold-based de-emphasis.
- Performance budgets (p95 target per test) via YAML/JSON file; dual guard (ratio + absolute) to reduce noise.
- JSON diff output + HTML panel + optional per-row badges.
- CI failure gating on selectable regression types (`--html-fail-on`).
- Stable deterministic output ordering; property-based invariant tests.

## Install
```
pip install pytest-html-baseline
# HTML panel & row badge integration (requires pytest-html):
pip install pytest-html pytest-html-baseline
```

### Optional Convenience CLI
Installing the package now also provides a `pytest-html-baseline` console script that mirrors the developer convenience found in `example_suite/quick.sh` but works in any project.

Examples:
```
# Run tests and capture snapshot labeled v1 (creates .artifacts/ by default)
pytest-html-baseline run v1

# Make changes, then run again
pytest-html-baseline run v2

# See behavioral diff (regressions, fixes, slower tests, etc.)
pytest-html-baseline diff v1 v2 --perf

# Include code-level diff if you keep versioned dirs (v1/, v2/)
pytest-html-baseline diff v1 v2 --code

# Only code diff
pytest-html-baseline code-diff v1 v2

# Run a sequence
pytest-html-baseline all v1 v2 v3

# List existing snapshots
pytest-html-baseline list
```

Flags (selected):
```
diff: --plain --full-ids --all --perf --perf-ratio R --perf-abs S --perf-show-faster \
	--code --code-only --versions-base DIR
run/all: --tests DIR --artifacts DIR --no-html --no-history (plus extra pytest args after --)
```
The CLI shells out to `pytest` adding the appropriate plugin flags; gating still occurs within pytest itself.

---

## Day-to-day workflow (copy & paste ready)

### 0) Install (once)
```
pip install pytest-html pytest-html-baseline
```

### 1) First run: create a baseline
Pick a folder for artifacts (e.g. `.artifacts/`).
```
pytest \
	--html=report_run1.html --self-contained-html \
	--html-save-baseline .artifacts/pytest_baseline.json
```
Outputs:
- `report_run1.html` – normal pytest-html report (if installed).
- `.artifacts/pytest_baseline.json` – compact snapshot (id, outcome, duration, fingerprint).

### 2) Day-to-day runs: compare to baseline (auto-triage)
```
pytest \
	--html=report_run2.html --self-contained-html \
	--html-baseline .artifacts/pytest_baseline.json \
	--html-save-baseline .artifacts/pytest_baseline.json \
	--html-diff-json .artifacts/pytest_diff.json \
	--html-fail-on new-failures \
	--html-slower-threshold-ratio 1.30 \
	--html-slower-threshold-abs 0.20
```
What happens automatically:
- Current run diffed vs baseline in O(n).
- Buckets: New Failures, Vanished Failures, Flaky Suspects, Slower Tests.
- Injects a "Baseline Compare" panel into the HTML report.
- Writes machine-readable diff JSON (`pytest_diff.json`).
- Fails build if there are non-flaky new failures (`--html-fail-on new-failures`).

Reading results:
- Open `report_run2.html` → Baseline Compare.
- New Failures: exactly what broke today (with fingerprint snippet).
- Slower Tests: which slowed and by how much (+Δms & ratio).
- Vanished Failures: what got fixed (useful for changelogs).
- Headless: parse `.artifacts/pytest_diff.json` in a bot/PR comment.

### 3) In CI (GitHub Actions example)
```yaml
name: tests
on: [push, pull_request]
jobs:
	test:
		runs-on: ubuntu-latest
		steps:
			- uses: actions/checkout@v4
			- uses: actions/setup-python@v5
				with: { python-version: "3.11" }
			- run: pip install -U pip pytest pytest-html pytest-html-baseline
			- run: mkdir -p .artifacts
			- name: Run tests with baseline compare
				run: |
					pytest \
						--html=report.html --self-contained-html \
						--html-baseline .artifacts/pytest_baseline.json \
						--html-save-baseline .artifacts/pytest_baseline.json \
						--html-diff-json .artifacts/pytest_diff.json \
						--html-fail-on new-failures \
						--html-slower-threshold-ratio 1.30 \
						--html-slower-threshold-abs 0.20
			- uses: actions/upload-artifact@v4
				with:
					name: test-artifacts
					path: |
						report.html
						.artifacts/pytest_baseline.json
						.artifacts/pytest_diff.json
```
Behavior:
- Green: no new (non-flaky) failures & no slowdowns beyond thresholds.
- Red: exit 1 with concise console summary. Open `report.html` → Baseline Compare for detail.

### 4) Make it really effective (tune noise)
Threshold tuning examples:
```
--html-slower-threshold-ratio 1.50   # only flag ≥50% slower
--html-slower-threshold-abs 0.50      # require +500ms absolute increase
```
Fail modes:
```
--html-fail-on new-failures | slower | budgets | any
```
Flake handling:
```
--html-flake-threshold 0.10   # stricter (treat fewer as flaky)
--html-flake-threshold 0.30   # more forgiving
```
Performance budgets (optional powerful add-on): create `tests/.perf_budgets.yaml`:
```yaml
budgets:
	tests/payments/test_checkout.py::test_payment: { p95: 0.80 }
```
Run with:
```
pytest ... --html-budgets tests/.perf_budgets.yaml --html-fail-on budgets
```
CI fails if observed p95 exceeds budget by ≥15% AND ≥50ms absolute (dual guard).

### 5) Typical workflows
A) Local dev (quick sanity):
```
pytest -q \
	--html-baseline .artifacts/pytest_baseline.json \
	--html-save-baseline .artifacts/pytest_baseline.json
```
B) Pre-merge speed focus:
```
pytest -q \
	--html-baseline .artifacts/pytest_baseline.json \
	--html-save-baseline .artifacts/pytest_baseline.json \
	--html-fail-on slower \
	--html-slower-threshold-ratio 1.25 \
	--html-slower-threshold-abs 0.10
```
C) Release guardrails (budgets):
```
pytest -q \
	--html-baseline .artifacts/pytest_baseline.json \
	--html-budgets tests/.perf_budgets.yaml \
	--html-fail-on budgets
```

### 6) Team adoption tips
- Pin a baseline on `main` after a stable run.
- Store artifacts (baseline, optional history jsonl) under `.artifacts/`.
- Surface results: upload `report.html` & diff JSON or post summary via bot.
- Start conservative (higher thresholds) → build trust → tighten gradually.

### 7) Troubleshooting
Problem | Adjustment
--- | ---
Slowdown seems tiny | Increase `--html-slower-threshold-abs` (e.g. 0.30–0.50)
Flaky tests causing failures | Raise `--html-flake-threshold` or use `--html-fail-on new-failures`
Not using pytest-html | Omit `--html=...`; JSON diff + exit gating still work
Too many slow warnings | Raise ratio or abs threshold (or both)
Need stricter gating | Use `--html-fail-on any`

---

## CLI Options
--html-save-baseline PATH : write snapshot after run
--html-baseline PATH       : load snapshot to diff
--html-diff-json PATH      : write diff JSON
--html-slower-threshold-ratio FLOAT (default 1.30 / env HTML_SLOWER_RATIO)
--html-slower-threshold-abs FLOAT seconds (default 0.20 / env HTML_SLOWER_ABS)
--html-min-count INT (default 0 / env HTML_MIN_COUNT)
--html-flake-threshold FLOAT (default 0.15 / env HTML_FLAKE_THRESHOLD)
--html-budgets PATH        : YAML/JSON performance budgets file
--html-fail-on {new-failures,slower,budgets,any} (default new-failures / env HTML_FAIL_ON)
--html-baseline-badges     : annotate pytest-html rows with badges
--html-baseline-verbose    : print example IDs for debugging

## JSON Snapshot Format
Single object: `version`, `created_at`, `collected`, `tests` (array of `{id,outcome,duration,sig}`). Failure fingerprint (`sig`) is a stable hash of the first normalized failure line.

## Diff JSON Structure (abridged)
```
{
	"new_failures": [{"id":...,"sig":...,"flake_score":...}],
	"vanished_failures": [...],
	"slower_tests": [{"id":...,"ratio":1.42,"abs_delta":0.231}],
	"budget_violations": [{"id":...,"budget_p95":0.8,"observed_p95":0.97}],
	"summary": {"n_new":1,"n_vanished":0,"n_flaky":0,"n_slower":2,"n_budget":1,"impact_score":6}
}
```

## Performance
Target: Diff 50k test pairs < 250ms wall, < 25MB RSS. Previous measurement (MacBook M-series, Python 3.13):
```
50k vs 50k tests diff: 41.8 ms wall, ~1.25 MB RSS delta
Summary example: {"n_new": 4404, "n_vanished": 4495, "n_flaky": 8899, "n_slower": 11222}
```
Benchmark helpers under `bench/` (CI runs a smaller smoke benchmark).

## Design Notes
- Dict index O(n) diff; no quadratic joins.
- Deterministic ordering for reproducibility.
- Property tests cover partition / monotonicity / idempotence.
- Flake scores: exponentially weighted from recent history (default threshold 0.15) to suppress noisy offenders.
- Dual-threshold slowness (ratio + absolute) to cut false positives.
- Impact score heuristic (weights new > budget > slower) for quick sorting.

## Example Synthetic Suite
See `example_suite/` for a three-iteration toy project (`v1` -> `v2` -> `v3`) plus a `demo_run.sh` script showing baseline creation, regression introduction, and budget violation detection with produced HTML & JSON artifacts.

## License
MIT
