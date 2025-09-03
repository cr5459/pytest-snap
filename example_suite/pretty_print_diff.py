#!/usr/bin/env python
"""Pretty-print a pytest-html-baseline diff JSON (e.g. diff_v2.json).

Usage examples:

  python example_suite/pretty_print_diff.py .artifacts/diff_v2.json
  python example_suite/pretty_print_diff.py .artifacts/diff_v3.json --limit 10 --no-color

If no path is given it defaults to .artifacts/pytest_diff.json
"""
from __future__ import annotations
import json, sys, argparse, pathlib
from typing import List, Dict

ANSI = {
    'red': '\x1b[31m',
    'green': '\x1b[32m',
    'yellow': '\x1b[33m',
    'cyan': '\x1b[36m',
    'bold': '\x1b[1m',
    'reset': '\x1b[0m'
}

def color(enabled: bool, name: str, text: str) -> str:
    if not enabled:
        return text
    return f"{ANSI.get(name,'')}{text}{ANSI['reset']}"

def fmt_list(items: List[Dict], key: str = 'id', limit: int = 20) -> List[str]:
    out = []
    for r in items[:limit]:
        ident = r.get(key, '?')
        extra_bits = []
        if 'sig' in r:
            extra_bits.append(r['sig'][:8])
        if 'ratio' in r:
            extra_bits.append(f"x{r['ratio']:.2f}")
        if 'abs_delta' in r:
            extra_bits.append(f"+{r['abs_delta']:.3f}s")
        if 'budget_p95' in r and 'observed_p95' in r:
            extra_bits.append(f"p95 {r['observed_p95']:.3f}>{r['budget_p95']:.3f}")
        suffix = (" [" + ", ".join(extra_bits) + "]") if extra_bits else ""
        out.append(f"- {ident}{suffix}")
    if len(items) > limit:
        out.append(f"  ... ({len(items)-limit} more)")
    if not out:
        out.append("(none)")
    return out

def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('diff', nargs='?', default='.artifacts/pytest_diff.json')
    ap.add_argument('--limit', type=int, default=20, help='max items per bucket')
    ap.add_argument('--no-color', action='store_true')
    args = ap.parse_args(argv)

    path = pathlib.Path(args.diff)
    if not path.exists():
        print(f"Diff file not found: {path}", file=sys.stderr)
        return 2
    diff = json.loads(path.read_text())
    summ = diff.get('summary', {})
    use_color = not args.no_color

    print(color(use_color, 'bold', f"Baseline Diff: {path}"))
    print(f"Summary: new={summ.get('n_new',0)} vanished={summ.get('n_vanished',0)} flaky={summ.get('n_flaky',0)} slower={summ.get('n_slower',0)} budgets={summ.get('n_budget',0)} impact={summ.get('impact_score','?')}")

    sections = [
        ('New Failures', 'red', diff.get('new_failures', [])),
        ('Vanished Failures', 'green', diff.get('vanished_failures', [])),
        ('Flaky Suspects', 'yellow', diff.get('flaky_suspects', [])),
        ('Slower Tests', 'cyan', diff.get('slower_tests', [])),
        ('Budget Violations', 'red', diff.get('budget_violations', [])),
    ]
    for title, col, items in sections:
        print('\n' + color(use_color, col, title + ':'))
        for line in fmt_list(items, limit=args.limit):
            print(line)
    return 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
