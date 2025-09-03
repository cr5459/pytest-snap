#!/usr/bin/env bash
# Convenience wrapper: formatted snapshot diff for any two labels.
# Usage: example_suite/diff_snap.sh v2 v3 [--all] [--plain] [--full-ids]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ART="$SCRIPT_DIR/.artifacts"
if [ $# -lt 2 ]; then
  echo "Usage: diff_snap.sh <a> <b> [compare options]" >&2
  exit 2
fi
A="$1"; B="$2"; shift 2
PA="$ART/snap_${A}.json"
PB="$ART/snap_${B}.json"
if [ ! -f "$PA" ]; then echo "Missing $PA (run quick.sh run $A)" >&2; exit 1; fi
if [ ! -f "$PB" ]; then echo "Missing $PB (run quick.sh run $B)" >&2; exit 1; fi
python "$SCRIPT_DIR/compare_snapshots.py" "$PA" "$PB" "$@"
