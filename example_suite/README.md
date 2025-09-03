# Example Synthetic Test Evolution

This directory contains three synthetic iterations (v1 -> v2 -> v3) of a small pytest suite to demonstrate how `pytest-html-baseline` surfaces changes: new failures, vanished failures, flaky suspects, slower tests, and performance budgets.

## Layout
- v1: initial green-ish baseline (1 intentional failure, one slower test, one random flake starter)
- v2: introduces a new failure, fixes prior failure (vanished), makes one test slower, adds intermittent flake behaviour
- v3: performance budget violation & another slowdown; flaky test stabilizes

## Usage
Create an artifacts directory first:
```
mkdir -p .artifacts
```

### 1. Establish baseline from v1
```
pytest example_suite/v1/tests \
  --html=.artifacts/v1.html --self-contained-html \
  --html-save-baseline .artifacts/pytest_baseline.json
```

### 2. Run v2 against baseline
```
pytest example_suite/v2/tests \
  --html=.artifacts/v2.html --self-contained-html \
  --html-baseline .artifacts/pytest_baseline.json \
  --html-save-baseline .artifacts/pytest_baseline.json \
  --html-diff-json .artifacts/diff_v2.json \
  --html-fail-on new-failures
```
Inspect `.artifacts/v2.html` Baseline Compare panel and `diff_v2.json`.

### 3. Optional budgets file
Create `example_suite/budgets.yaml`:
```yaml
budgets:
  example_suite/v2/tests/test_perf.py::test_fast_enough: { p95: 0.05 }
  example_suite/v3/tests/test_perf.py::test_fast_enough: { p95: 0.05 }
```

### 4. Run v3 with budgets & stricter gating
```
pytest example_suite/v3/tests \
  --html=.artifacts/v3.html --self-contained-html \
  --html-baseline .artifacts/pytest_baseline.json \
  --html-save-baseline .artifacts/pytest_baseline.json \
  --html-diff-json .artifacts/diff_v3.json \
  --html-budgets example_suite/budgets.yaml \
  --html-fail-on any
```

Observe new failures, vanished failures (if any), slower tests, and any budget violations.

### 5. Demonstrate flakiness handling
Run v2 twice:
```
pytest example_suite/v2/tests --html-baseline .artifacts/pytest_baseline.json --html-save-baseline .artifacts/pytest_baseline.json
pytest example_suite/v2/tests --html-baseline .artifacts/pytest_baseline.json --html-save-baseline .artifacts/pytest_baseline.json
```
The intermittently failing test will accumulate history to raise its flake score; above threshold it won't fail the build under `--html-fail-on new-failures`.

---
Feel free to modify delays or random seeds to explore behavior.
