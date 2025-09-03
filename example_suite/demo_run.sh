#!/usr/bin/env bash
set -euo pipefail
ART_DIR=.artifacts
mkdir -p "$ART_DIR"

echo "== Baseline (v1) =="
pytest example_suite/v1/tests \
  --html=$ART_DIR/v1.html --self-contained-html \
  --html-save-baseline $ART_DIR/pytest_baseline.json || true

echo "== Compare (v2) =="
pytest example_suite/v2/tests \
  --html=$ART_DIR/v2.html --self-contained-html \
  --html-baseline $ART_DIR/pytest_baseline.json \
  --html-save-baseline $ART_DIR/pytest_baseline.json \
  --html-diff-json $ART_DIR/diff_v2.json \
  --html-fail-on new-failures || true

cat > example_suite/budgets.yaml <<'EOF'
budgets:
  example_suite/v3/tests/test_perf.py::test_fast_enough: { p95: 0.05 }
  example_suite/v3/tests/test_perf.py::test_already_slow: { p95: 0.18 }
EOF

echo "== Compare (v3 with budgets) =="
pytest example_suite/v3/tests \
  --html=$ART_DIR/v3.html --self-contained-html \
  --html-baseline $ART_DIR/pytest_baseline.json \
  --html-save-baseline $ART_DIR/pytest_baseline.json \
  --html-diff-json $ART_DIR/diff_v3.json \
  --html-budgets example_suite/budgets.yaml \
  --html-fail-on any || true

echo "Artifacts in $ART_DIR:" && ls -1 $ART_DIR
