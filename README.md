# pytest-snap

Minimal deterministic snapshot capture of a pytest run: per-test outcome +
duration (ns) stored in a JSON file. Intended as a small foundation for
optional future diff / perf / gating features.

Current 0.1.0 scope:
* Pytest plugin auto‑loaded (entry point `snap`).
* `--snap` flag enables capture.
* `--snap-out PATH` chooses output file (default `.snap/current.json`).
* CLI wrapper for repeated labeled runs (`pytest-snap run`, `pytest-snap all`).

Out of scope (planned, not implemented yet in the plugin runtime): budgets,
flake scoring, inline performance gating, historical diffing inside the test
session. The README will grow with those features post‑0.1.0.

---

## Installation

```bash
pip install pytest-snapcheck
```
---

## Quick Start

Install:

```bash
pip install pytest-snapcheck
```

Run tests with snapshot capture:

```bash
pytest --snap
```

Result written to `.snap/current.json` (create the directory if needed). Change
destination:

```bash
pytest --snap --snap-out my_run.json
```

Use the helper CLI for labeled runs (writes `.artifacts/snap_<label>.json`):

```bash
pytest-snap run v1
pytest-snap run v2
# or
pytest-snapcheck run v1
```

Generate several labels in sequence:

```bash
pytest-snap all               # default labels v1 v2 v3
```

### Using a custom tests folder

By default, the CLI runs your repo's `./tests` directory if it exists. To target a different folder, file, or a single test (node id), pass `--tests`:

```bash
# A specific directory
pytest-snap run v1 --tests ./path/to/tests

# A subfolder of your test tree
pytest-snap run v1 --tests tests/integration

# A single file or a single test node
pytest-snap run v1 --tests tests/test_api.py
pytest-snap run v1 --tests tests/test_api.py::test_happy_path

# Add regular pytest filters (forwarded as-is)
pytest-snap run v1 --tests tests/integration -k "smoke" -m "not flaky"
```

Prefer using plain pytest? The plugin doesn't change discovery; just supply paths as usual and add the flags:

```bash
pytest --snap --snap-out .artifacts/snap.json ./path/to/tests
# If plugin autoload is disabled:
pytest -p pytest_snap.plugin --snap --snap-out .artifacts/snap.json ./path/to/tests
```

### Artifacts and outputs

Where results are written by default and how to change it:

- Pure pytest (plugin)
	- Default file: `.snap/current.json`
	- Override with `--snap-out PATH`.
	- Example:
		```bash
		pytest --snap --snap-out .artifacts/snap_v1.json tests/
		```

- CLI (pytest-snap)
	- Default directory: `.artifacts`
	- Files created per run:
		- `.artifacts/snap_<label>.json` (always)
		- `.artifacts/run_<label>.html` (only with `--html` and pytest-html installed)
	- Change directory with `--artifacts DIR`.
	- Examples:
		```bash
		# Default outputs
		pytest-snap run v1

		# Custom output directory
		pytest-snap run v1 --artifacts out/snapshots

		# Diff reads from the same directory
		pytest-snap diff v1 v2 --artifacts out/snapshots
		```

- Housekeeping helpers
	```bash
	pytest-snap list                # list available snapshots
	pytest-snap show v1            # show summary for a snapshot
	pytest-snap clean              # remove the artifacts directory
	# (all accept --artifacts DIR)
	```

---

## Snapshot Schema (v0.1.0)

```json
{
	"started_ns": 1234567890,
	"finished_ns": 1234569999,
	"env": {"pytest_version": "8.x"},
	"results": [
		{"nodeid": "tests/test_example.py::test_ok", "outcome": "passed", "dur_ns": 10423}
	]
}
```

## Future Roadmap (High Level)
Planned incremental additions (subject to change):
1. Baseline diff & change bucket summarization.
2. Slower test detection & perf thresholds.
3. Budget YAML support and gating.
4. Historical flake scoring.
5. Rich diff / timeline CLI views.

Early adopters should pin minor versions if depending on emerging fields.

### Code-level Diff (`--code`)

In addition to outcome & timing changes you can compare the test function source between two labeled versions.

Typical layout:
```
project/
	v1/tests/...
	v2/tests/...
```

Run a snapshot diff including code changes:
```bash
pytest-snap diff v1 v2 --code
```

What happens:
* Auto-detects version directories `<A>` and `<B>` under the current working directory (or under `--versions-base` if provided).
* Lists added / removed / modified test functions (`def test_*`).
* Shows a unified diff (syntax-colored) for modified tests with simple performance hints (range() growth, added sleep time).

Options:
* `--code`        Combine snapshot diff + code diff.
* `--code-only`   Suppress snapshot outcome section; only show code diff.
* `--versions-base DIR`   Look for version subdirectories under `DIR` instead of `.`.

Examples:
```bash
# Just code changes (no outcome buckets)
pytest-snap diff v1 v2 --code-only --code

# Custom versions base path
pytest-snap diff release_old release_new --code --versions-base ./releases

# Code + performance analysis together
pytest-snap diff v1 v2 --code --perf
```

Limitations:
* Only inspects top-level `test_*.py` files; helper modules not diffed.
* Function-level granularity (class-based tests appear as functions with node ids).
* Large diffs are truncated after 20 modified tests (increase by editing source if needed).

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

### Timeline / Historical Progression (`timeline` subcommand)

Use the timeline view to see how snapshots evolved over time and when failures first appeared.

Create snapshots (labels arbitrary):
```bash
pytest-snap run v1
pytest-snap run v2
pytest-snap run v3
```

Show chronological summary:
```bash
pytest-snap timeline
```
Sample output:
```
TIMELINE (3 snapshots)
2025-09-04T19:20:21Z v1 commit=8e05100 total=28 fail=0 new_fail=0 fixes=0 regressions=0
2025-09-04T19:25:07Z v2 commit=8e05100 total=28 fail=1 new_fail=1 fixes=0 regressions=1
2025-09-04T19:30:44Z v3 commit=8e05100 total=28 fail=1 new_fail=0 fixes=1 regressions=0
```

Flags:
| Flag | Purpose |
|------|---------|
| `--since <commit>` | Start listing from first snapshot whose `git_commit` matches (short hash) |
| `--limit N` | Show only the last N snapshots after filtering |
| `--json` | Emit machine-readable JSON array |
| `--artifacts DIR` | Use alternate artifacts directory |

Computed per row (vs previous snapshot):
* `new_fail`: tests that newly failed.
* `fixes`: previously failing tests that now pass.
* `regressions`: passed → failed transitions.

Metadata:
* Each snapshot is enriched (best effort) with `git_commit` (short HEAD hash) after write.
* If git metadata isn’t available (outside a repo), the commit shows as `unknown` or `None`.

JSON example:
```bash
pytest-snap timeline --json | jq .
```
Produces entries like:
```json
[
	{"label":"v1","git_commit":"8e05100","total":28,"failed":0,"passed":28,"xfailed":0,"xpassed":0,"new_fail":0,"fixes":0,"regressions":0},
	{"label":"v2","git_commit":"8e05100","total":28,"failed":1,"passed":27,"xfailed":0,"xpassed":0,"new_fail":1,"fixes":0,"regressions":1}
]
```

Use cases:
* Quickly pinpoint when a regression first appeared before diving into full diff.
* Send the timeline JSON straight to a small dashboard (Prometheus push, simple web chart) without re-reading all snapshot files.
* In Continuous Integration (CI) pipelines, fail the run (block the merge) if the timeline shows new failures or regressions. CI = automated test/build system that runs on every change.

### Labels vs paths (what does `v1` mean?)

- `pytest-snap run <label>`
	- The label only names the output file: `.artifacts/snap_<label>.json`.
	- It does not select a folder named `<label>`; discovery defaults to `./tests` unless you pass `--tests`.
	- Examples:
		```bash
		pytest-snap run v1                      # runs ./tests, writes .artifacts/snap_v1.json
		pytest-snap run mylabel --tests tests/api
		pytest-snap run pr-123  --tests tests/test_api.py::test_happy_path
		```

- `pytest-snap diff <A> <B>`
	- Labels refer to snapshot files in the artifacts directory (default `.artifacts`).
	- When you add `--code` (or `--code-only`), directories named `<A>` and `<B>` are looked up under `--versions-base` (default `.`).
	- You can control the base with `--versions-base PATH`.

---

## Flaky Detection

When history logging is enabled (default in `pytest-snap run`), previous outcomes are tracked. A weighted score measures pass ↔ fail flips. Highly flaky tests can be excluded from "new failures" to reduce noise.

---

## Conceptual Model
1. Enable capture (flag / CLI) → write snapshot.
2. (Future) Compare snapshots → categorize changes.
3. (Future) Apply gating policies.
4. Refresh baseline as intent changes.

---

## FAQ
**Do I need the CLI?** No; it's convenience sugar for labeled runs.

**Why not a baseline diff yet?** Keeping 0.1.0 deliberately small; diffing lands next.

**Will the schema change?** Potentially (still pre-1.0.0) but additions will prefer backward compatibility.

---

## Glossary
| Term | Definition |
|------|------------|
| Snapshot | JSON record of one full test run |
| Nodeid | Pytest's canonical test identifier |
| Duration | Test call-phase elapsed time (ns stored) |

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

