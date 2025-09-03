#!/usr/bin/env bash
set -euo pipefail

# Minimal, opinionated helper.
# Philosophy ("Jane Street style"):
#  - Single responsibility per command
#  - Idempotent where practical
#  - Explicit inputs, explicit outputs
#  - No hidden mutation of an "accepted baseline"; every run is a snapshot

SELF_SRC="${BASH_SOURCE[0]}"
SCRIPT_DIR="$(cd "$(dirname "$SELF_SRC")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR"/.. && pwd)"
cd "$REPO_ROOT"

ART="$SCRIPT_DIR/.artifacts"
mkdir -p "$ART"

usage() {
  cat <<'EOF'
Usage: example_suite/quick.sh <command> [args]

Commands:
  init                   Ensure artifacts dir exists; show location.
  run <label>            Run tests (single directory) and write snapshot: snap_<label>.json
  v1|v2|v3               Convenience aliases (run v1, etc.)
  all [labels...]        Run multiple labels sequentially (default: v1 v2 v3)
  diff <a> <b> [opts]    Diff two labeled snapshots (a -> b). Extra flags:
                           --plain / --no-color  disable color (snapshot diff)
                           --full-ids            show full node ids
                           --all                 show all persistent passes
                           --perf                include slower test analysis (ratio>=1.3 & +0.05s default)
                           --perf-ratio R        override slower ratio threshold
                           --perf-abs S          override slower absolute seconds threshold
                           --perf-show-faster    also list significantly faster tests
                           --code                also run code-level diff (if dirs example_suite/<a>, <b> exist)
                           --code-only           only run code-level diff
  clean                  Remove artifacts directory.

Model:
  Single source of tests: example_suite/tests
  Each run with a label captures state into .artifacts/snap_<label>.json
  Edit code/tests between runs to create meaningful diffs.

Artifacts:
  .artifacts/snap_<label>.json  Snapshot for that label
  .artifacts/run_<label>.html   HTML report (if pytest-html installed)

Typical flow:
  run v1   # baseline
  make changes
  run v2   # new state
  diff v1 v2
EOF
}

is_valid_label() {
  [[ "$1" =~ ^[A-Za-z0-9._-]+$ ]]
}

run_labeled() {
  local label="$1"
  if ! is_valid_label "$label"; then
    echo "Invalid label '$label' (allowed: alnum . _ -)" >&2; exit 1
  fi
  local test_dir="example_suite/tests"
  if [ ! -d "$test_dir" ]; then
    echo "Missing tests directory: $test_dir" >&2; exit 1
  fi
  local snap="$ART/snap_${label}.json"
  local html="$ART/run_${label}.html"
  echo "== RUN $label -> $snap =="
  pytest "$test_dir" \
    --html="$html" \
    --self-contained-html \
    --html-save-baseline "$snap" \
    --html-history-path "$ART/history.jsonl" || true
  if [ ! -s "$snap" ]; then
    echo "Snapshot not created (possibly zero tests?)." >&2; exit 1
  fi
  echo "Saved snapshot: $snap"
}

diff_snapshots() {
  local A="$1"; local B="$2"; shift 2
  local PA="$ART/snap_${A}.json"
  local PB="$ART/snap_${B}.json"
  if [ ! -f "$PA" ]; then echo "Missing snapshot $PA (run $A first)" >&2; exit 1; fi
  if [ ! -f "$PB" ]; then echo "Missing snapshot $PB (run $B first)" >&2; exit 1; fi
  echo "== DIFF $A -> $B =="
  python example_suite/compare_snapshots.py "$PA" "$PB" "$@" || true
}

code_version_diff() {
  local A="$1"; local B="$2"
  local DIR_A="example_suite/$A"
  local DIR_B="example_suite/$B"
  if [ ! -d "$DIR_A" ] || [ ! -d "$DIR_B" ]; then
    echo "(code diff skipped: missing directories $DIR_A or $DIR_B)" >&2
    return 0
  fi
  echo "== CODE DIFF $A -> $B =="
  python example_suite/code_version_diff.py "$DIR_A" "$DIR_B" || true
}

cmd=${1:-help}
case "$cmd" in
  help|-h|--help)
    usage ;;
  init)
    echo "Artifacts dir: $ART" ;;
  run)
    label=${2:-}; if [ -z "${label}" ]; then echo "Usage: quick.sh run <label>" >&2; exit 1; fi
    run_labeled "$label" ;;
  v1|v2|v3)
    run_labeled "$cmd" ;;
  all)
    shift || true
    if [ $# -eq 0 ]; then
      seq_labels=(v1 v2 v3)
    else
      seq_labels=("$@")
    fi
    for lbl in "${seq_labels[@]}"; do
      echo "-- all: running $lbl --"
      run_labeled "$lbl"
    done
    ;;
  diff)
    if [ $# -lt 3 ]; then echo "Usage: quick.sh diff <a> <b> [flags]" >&2; exit 1; fi
    A="$2"; B="$3"; shift 3
    code=false
    code_only=false
    snap_args=()
    while [ $# -gt 0 ]; do
      case "$1" in
        --code) code=true ;;
        --code-only) code_only=true; code=true ;;
        --all|--plain|--no-color|--full-ids) snap_args+=("$1") ;;
        *) snap_args+=("$1") ;;
      esac
      shift || true
    done
    if [ "$code_only" = false ]; then
      if [ "${#snap_args[@]:-0}" -gt 0 ]; then
        diff_snapshots "$A" "$B" "${snap_args[@]}"
      else
        diff_snapshots "$A" "$B"
      fi
    fi
    if [ "$code" = true ]; then
      code_version_diff "$A" "$B"
    fi
    ;;
  clean)
    if [ -d "$ART" ]; then
      rm -rf "$ART"
      echo "Removed $ART directory."
    else
      echo "No artifacts directory to remove ($ART)."
    fi ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage
    exit 1 ;;
esac
