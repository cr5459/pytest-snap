#!/usr/bin/env python
"""Colorful, structured diff between two version directories (e.g. v1 v2).

Focuses on test_*.py files:
  * Detects added / removed / modified test functions
  * Shows compact colored unified diffs for modified tests
  * Heuristics for perf-oriented changes (range() loop work or time.sleep delta)
  * Optional plain output (no ANSI) with --no-color

Usage:
  python example_suite/code_version_diff.py v1 v2
  python example_suite/code_version_diff.py v1 v2 --limit 5
  python example_suite/code_version_diff.py v1 v2 --no-color > report.txt
"""
from __future__ import annotations
import argparse, ast, difflib, pathlib, re, sys, textwrap
from dataclasses import dataclass
from typing import Dict, List, Tuple

ANSI = {
    'red': '\x1b[31m',
    'green': '\x1b[32m',
    'yellow': '\x1b[33m',
    'blue': '\x1b[34m',
    'magenta': '\x1b[35m',
    'cyan': '\x1b[36m',
    'bold': '\x1b[1m',
    'dim': '\x1b[2m',
    'reset': '\x1b[0m'
}

def C(enabled: bool, color: str, text: str) -> str:
    if not enabled:
        return text
    return f"{ANSI.get(color,'')}{text}{ANSI['reset']}"

@dataclass
class TestFunc:
    file: pathlib.Path
    name: str          # function name
    qual: str          # file::name
    source: List[str]  # raw source lines including def ...

# Python 3.8 ast has end_lineno; fall back gracefully if absent

def extract_tests(path: pathlib.Path) -> Dict[str, TestFunc]:
    code = path.read_text().splitlines(keepends=True)
    try:
        tree = ast.parse(''.join(code))
    except SyntaxError:
        return {}
    out: Dict[str, TestFunc] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
            start = getattr(node, 'lineno', 1) - 1
            end = getattr(node, 'end_lineno', None)
            if end is None:
                # naive scan until blank line or next def
                end = start + 1
                while end < len(code) and not code[end].startswith('def '):
                    end += 1
            snippet = code[start:end]
            qual = f"{path.name}::{node.name}"
            out[qual] = TestFunc(file=path, name=node.name, qual=qual, source=snippet)
    return out

R_RANGE = re.compile(r"range\((\d+)\)")
R_SLEEP = re.compile(r"time\.sleep\((\d+\.?\d*)\)")

def perf_hints(old: List[str], new: List[str]) -> List[str]:
    hints = []
    old_ranges = list(map(int, R_RANGE.findall(''.join(old))))
    new_ranges = list(map(int, R_RANGE.findall(''.join(new))))
    if old_ranges and new_ranges:
        if sum(new_ranges) > sum(old_ranges):
            ratio = (sum(new_ranges) / max(1, sum(old_ranges)))
            hints.append(f"range workload ↑ x{ratio:.2f} ({sum(old_ranges)}→{sum(new_ranges)})")
    old_sleep = [float(x) for x in R_SLEEP.findall(''.join(old))]
    new_sleep = [float(x) for x in R_SLEEP.findall(''.join(new))]
    if old_sleep and new_sleep:
        if sum(new_sleep) > sum(old_sleep):
            delta = sum(new_sleep) - sum(old_sleep)
            hints.append(f"sleep total ↑ +{delta:.3f}s ({sum(old_sleep):.3f}→{sum(new_sleep):.3f})")
    return hints

def unified_function_diff(a: List[str], b: List[str], color: bool) -> List[str]:
    diff = list(difflib.unified_diff(a, b, fromfile='a', tofile='b', n=3))
    out: List[str] = []
    for line in diff:
        if line.startswith('---') or line.startswith('+++'):
            continue
        if line.startswith('@@'):
            out.append(C(color, 'magenta', line.rstrip()))
        elif line.startswith('+'):
            out.append(C(color, 'green', line.rstrip()))
        elif line.startswith('-'):
            out.append(C(color, 'red', line.rstrip()))
        else:
            out.append(C(color, 'dim', line.rstrip()))
    return out

def collect(dir_path: pathlib.Path) -> Dict[str, TestFunc]:
    tests: Dict[str, TestFunc] = {}
    for p in sorted(dir_path.glob('test_*.py')):
        tests.update(extract_tests(p))
    return tests

def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description='Structured colorful code-level test diff')
    ap.add_argument('old')
    ap.add_argument('new')
    ap.add_argument('--limit', type=int, default=20, help='limit modified test detailed diffs')
    ap.add_argument('--no-color', action='store_true')
    args = ap.parse_args(argv)

    a_dir = pathlib.Path(args.old)
    b_dir = pathlib.Path(args.new)
    if not a_dir.is_dir() or not b_dir.is_dir():
        print('Both arguments must be directories', file=sys.stderr)
        return 2

    use_color = not args.no_color and sys.stdout.isatty()

    tests_a = collect(a_dir)
    tests_b = collect(b_dir)

    keys_a = set(tests_a)
    keys_b = set(tests_b)

    added = sorted(keys_b - keys_a)
    removed = sorted(keys_a - keys_b)
    common = sorted(keys_a & keys_b)

    modified: List[Tuple[str, TestFunc, TestFunc]] = []
    for k in common:
        if tests_a[k].source != tests_b[k].source:
            modified.append((k, tests_a[k], tests_b[k]))

    print(C(use_color, 'bold', f"Code Version Diff: {a_dir.name} → {b_dir.name}"))
    print(f"Files scanned: {len(set(t.file for t in tests_a.values()))} → {len(set(t.file for t in tests_b.values()))}")
    print(f"Tests: total {len(tests_a)} → {len(tests_b)} | added {len(added)} removed {len(removed)} modified {len(modified)}")

    def bullet(lst, col):
        if not lst:
            print(C(use_color, col, '  (none)'))
            return
        for item in lst:
            print(C(use_color, col, f"  - {item}"))

    print('\n' + C(use_color, 'green', 'Added Tests:'))
    bullet(added, 'green')
    print('\n' + C(use_color, 'red', 'Removed Tests:'))
    bullet(removed, 'red')
    print('\n' + C(use_color, 'yellow', 'Modified Tests:'))
    if not modified:
        print(C(use_color, 'yellow', '  (none)'))
    else:
        for idx, (qual, old, new) in enumerate(modified):
            if idx >= args.limit:
                print(f"  ... ({len(modified) - args.limit} more omitted)" )
                break
            hints = perf_hints(old.source, new.source)
            hint_txt = (' ' + ', '.join(hints)) if hints else ''
            print(C(use_color, 'bold', f"  * {qual}{hint_txt}"))
            for line in unified_function_diff(old.source, new.source, use_color):
                print('    ' + line)
    print()
    print(C(use_color, 'cyan', 'Summary:'))
    print(textwrap.fill(
        f"Added {len(added)}, Removed {len(removed)}, Modified {len(modified)} tests. "
        f"Perf hints flagged in {sum(1 for _,o,n in modified if perf_hints(o.source,n.source))} modified tests.",
        width=100))
    return 0

if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
