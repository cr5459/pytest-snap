# pytest-snap

A lightweight way to record the results of a test run (a snapshot) and later compare new runs against that baseline. It highlights regressions (new failures), fixes, removed tests, performance slow‑downs, flaky behavior, and optional performance budget breaches.

The project provides:

1. A pytest plugin (auto‑loaded once installed).  
2. A helper CLI (`pytest-snap`) for labeled runs and offline diffs.

Use either one or both— they are complementary but independent.

---

## Installation

```bash
pip install pytest-snap
```
---

## Helper CLI (`pytest-snap`)

Labeled runs make comparisons simple (e.g. `v1`, `v2`).

```bash
# Run default sequence (v1 v2 v3)
pytest-snap all

# Or run individual labels
pytest-snap run v1
pytest-snap run v2

# Compare two snapshots (v1 -> v2) with performance analysis
pytest-snap diff v1 v2 --perf

# Show a single snapshot summary
pytest-snap show v2

# Remove generated artifacts
pytest-snap clean
```

Snapshots live in `.artifacts/` as `snap_<label>.json`. Add `--html` to `run`/`all` to also emit a pytest-html report (if `pytest-html` is installed). The CLI is unchanged by the flag rename. More on the --perf flag in advanced features section.

---

## Tracked Change Categories

| Category | Description |
|----------|-------------|
| New failures | Tests that now fail but did not previously |
| Fixed failures | Tests that failed before and now pass |
| Vanished failures | Former failing tests that are now gone or fixed |
| Slower tests | Same test now significantly slower |
| Flaky suspects | Tests whose outcome flips between runs |
| New / resolved / persistent xfails | Expected-failure state transitions |
| XPASS | Tests marked xfail that unexpectedly passed |
| Budget violations | Defined performance budget exceeded |

---
## Advanced Features

The following sections dive into optional and more advanced capabilities: performance budgets and gating, performance diff analysis, flaky detection heuristics, and baseline workflow refinements. Skip ahead only if you need tighter CI controls or deeper performance insight.

## Performance Budgets

Define timing expectations for groups of tests using a YAML file. Example `budgets.yaml`:

```yaml
groups:
  core:
	 match: "tests/"   # substring match in test id
	 p95: 0.50         # 95th percentile < 0.50s
  slow_group:
	 match: "tests/slow_"
	 max_avg: 1.2      # mean duration < 1.2s
```

Use it:
```bash
pytest --snap-baseline .artifacts/snap_base.json \
	--snap-budgets budgets.yaml \
	--snap-fail-on budgets
```
Legacy form (still accepted): `--html-baseline ... --html-budgets ... --html-fail-on budgets`.

---

### Performance Diff (`--perf`) in the CLI

The CLI snapshot diff (`pytest-snap diff A B`) ignores timing changes unless you opt in:

```bash
pytest-snap diff v1 v2 --perf
```

This adds a "Slower Tests" section listing tests whose elapsed time increased beyond BOTH thresholds:

* ratio: new_duration / old_duration >= `--perf-ratio` (default 1.30 ⇒ at least 30% slower)
* absolute: new_duration - old_duration >= `--perf-abs` (default 0.05s)

Optional flags:

| Flag | Meaning |
|------|---------|
| `--perf-ratio 1.5` | Require 50%+ slow-down (instead of 30%) |
| `--perf-abs 0.02` | Require at least 20ms added latency |
| `--perf-show-faster` | Also list significantly faster tests |

To see only timings + code changes (skip outcome buckets):
```bash
pytest-snap diff v1 v2 --perf --code --code-only
```

### Performance Gating During Test Runs

Inside pytest runs (plugin), slower tests are tracked when you supply a baseline and choose a fail mode:

```bash
pytest --snap-baseline .artifacts/snap_base.json \
	--snap-fail-on slower \
	--snap-slower-threshold-ratio 1.25 \
	--snap-slower-threshold-abs 0.10
```

Behavior:

* A test is considered slower if it exceeds both the ratio and absolute thresholds.
* `--snap-fail-on slower` turns any slower test into a non‑zero exit (CI gating).
* Adjust thresholds to tune sensitivity (raise ratio or abs to reduce noise).

Shortcut mental model: ratio filters relative regressions; absolute filters micro‑noise. Both must pass so a 2ms blip on a 1µs test won't alert even if ratio is large.

If you only care about functional changes, omit perf flags; if you want early perf regression visibility, add them.

---

## Flaky Detection

When history logging is enabled (default in `pytest-snap run`), previous outcomes are tracked. A weighted score measures pass ↔ fail flips. Highly flaky tests can be excluded from "new failures" to reduce noise.

---

## Conceptual Model

1. Capture a baseline snapshot.  
2. Compare new runs to that baseline.  
3. Choose gating rules.  
4. Refresh the baseline when the current state is the new normal.  

---

## FAQ

**Do I need the CLI?** No. The plugin alone works; the CLI adds convenience for labeled runs and offline diffs.

**When do I refresh the baseline?** After intentional changes when remaining differences are acceptable.

**What about flaky tests?** Fix them ideally; meanwhile history-based filtering reduces false alarms.

**Is this a snapshot testing library for function outputs?** No. It snapshots test outcomes and timings.

**Does it speed up tests?** No—it surfaces regressions sooner.


```

---

## Glossary

| Term | Definition |
|------|------------|
| Snapshot | JSON record of one full test run |
| Baseline | The snapshot future runs are compared against |
| Diff | Structured comparison of baseline vs current run |
| Flaky test | Test with unstable pass/fail result across runs |
| Budget | Performance rule (e.g. max average or p95) |

---

## Contributing

1. Fork / clone.  
2. (Optional) Create venv & install: `pip install -e .[dev]`.  
3. Add or adjust tests for your changes.  
4. Keep documentation clear and concise.  
5. Open a PR.

---

## License

MIT (see `LICENSE`).

---

Happy hacking.

---

