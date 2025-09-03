#!/usr/bin/env python
"""Compare two saved snapshot JSON files (baseline-format) without re-running tests.

Usage:
  python example_suite/compare_snapshots.py [--plain] path/to/snap_a.json path/to/snap_b.json

Outputs colorized classification of differences:
  - Regressions, Fixes, Added Passing/Failing, Removed, Persistent, XFails transitions.

Set NO_COLOR or use --plain to disable ANSI colors.
"""
from __future__ import annotations
import json, sys, os


def load(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def index(snapshot):
    return {t['id']: t for t in snapshot.get('tests', [])}


def supports_color(force_plain: bool) -> bool:
    if force_plain:
        return False
    if os.environ.get('NO_COLOR') is not None:
        return False
    return sys.stdout.isatty()


class Palette:
    def __init__(self, enabled: bool):
        if not enabled:
            self.RESET = self.GREEN = self.RED = self.YELLOW = self.CYAN = self.BOLD = ''
        else:
            self.RESET = '\x1b[0m'
            self.GREEN = '\x1b[32m'
            self.RED = '\x1b[31m'
            self.YELLOW = '\x1b[33m'
            self.CYAN = '\x1b[36m'
            self.BOLD = '\x1b[1m'

    def c(self, color: str, text: str) -> str:
        return getattr(self, color) + text + self.RESET if getattr(self, color) else text


def main(a: str, b: str, *, plain: bool = False, show_all: bool = False, full_ids: bool = False,
         perf: bool = False, perf_ratio: float = 1.3, perf_abs: float = 0.05, perf_show_faster: bool = False) -> int:
    A = load(a); B = load(b)
    pal = Palette(supports_color(plain))
    ia, ib = index(A), index(B)

    regressions = []          # passed -> failed
    fixes = []                # failed -> passed
    persistent_fail = []      # failed -> failed
    persistent_pass = []      # passed -> passed
    added_pass = []           # only in B, passed
    added_fail = []           # only in B, failed
    removed = []              # only in A (any outcome)
    new_xfails = []           # new xfail
    resolved_xfails = []      # xfail -> passed

    for tid, rec in ia.items():
        if tid not in ib:
            removed.append((tid, rec.get('outcome')))
            continue
        cur = ib[tid]
        prev_out, cur_out = rec.get('outcome'), cur.get('outcome')
        if prev_out == 'passed' and cur_out == 'failed':
            regressions.append(tid)
        elif prev_out == 'failed' and cur_out == 'passed':
            fixes.append(tid)
        elif prev_out == 'failed' and cur_out == 'failed':
            persistent_fail.append(tid)
        elif prev_out == 'passed' and cur_out == 'passed':
            persistent_pass.append(tid)
        if prev_out in {'xfailed','xfail'} and cur_out == 'passed':
            resolved_xfails.append(tid)
        if prev_out not in {'xfailed','xfail'} and cur_out in {'xfailed','xfail'}:
            new_xfails.append(tid)

    for tid, rec in ib.items():
        if tid in ia:
            continue
        (added_fail if rec.get('outcome') == 'failed' else added_pass).append(tid)
        if rec.get('outcome') in {'xfailed','xfail'}:
            new_xfails.append(tid)

    # Optional performance analysis (snapshot durations) --------------------------------------------------
    slower = []   # (id, old_dur, new_dur, ratio, delta)
    faster = []  # only if perf_show_faster
    if perf:
        for tid in sorted(set(ia) & set(ib)):
            o = ia[tid].get('duration')
            n = ib[tid].get('duration')
            if isinstance(o, (int, float)) and isinstance(n, (int, float)):
                if n > o and (n / (o or 1e-9)) >= perf_ratio and (n - o) >= perf_abs:
                    slower.append((tid, o, n, n / (o or 1e-9), n - o))
                elif perf_show_faster and o > n and (o / (n or 1e-9)) >= perf_ratio and (o - n) >= perf_abs:
                    faster.append((tid, o, n, o / (n or 1e-9), o - n))

    total_changed = sum(map(len, [fixes, regressions, added_pass, added_fail, removed, new_xfails, resolved_xfails]))
    base_a, base_b = os.path.basename(a), os.path.basename(b)
    header = f"SNAPSHOT DIFF {base_a} -> {base_b}"
    print(pal.c('BOLD', pal.c('CYAN', header)))
    print(pal.c('CYAN', '-' * len(header)))

    # Build shortening map (function name only) unless disabled
    def short(tid: str) -> str:
        if full_ids:
            return tid
        # typical nodeid pattern: path::test_func[params]
        core = tid.split('::')[-1]
        return core

    # Disambiguate duplicates: if shortened names collide, append file stem
    if not full_ids:
        counts = {}
        for coll in [regressions, fixes, persistent_fail, persistent_pass, added_pass, added_fail, removed, new_xfails, resolved_xfails]:
            for entry in coll:
                tid = entry[0] if isinstance(entry, tuple) else entry
                s = short(tid)
                counts[s] = counts.get(s, 0) + 1

        def disamb(tid: str) -> str:
            s = short(tid)
            if counts.get(s, 0) > 1:
                # include file stem for clarity
                file_part = tid.split('::')[0].rsplit('/', 1)[-1]
                return f"{file_part}::{s}"
            return s
    else:
        def disamb(tid: str) -> str:  # type: ignore
            return tid

    def sect(title, items, color, label_fmt, limit=20):
        if not items:
            return
        print(pal.c(color, f"{title}: {len(items)}"))
        for t in items[:limit]:
            # t may be tuple (removed bucket)
            if isinstance(t, tuple):
                tid, extra = t
                label = label_fmt.format(f"{disamb(tid)} ({extra})")
            else:
                label = label_fmt.format(disamb(t))
            print(pal.c(color, f"  {label}"))
        if len(items) > limit:
            print(pal.c(color, f"  … ({len(items)-limit} more)"))

    # Order: negatives first, positives, neutrals
    sect("Regressions (passed→failed)", regressions, 'RED', 'REGRESSED: {}')
    sect("Added Failing Tests", added_fail, 'RED', 'ADDED FAIL: {}')
    sect("New XFails", new_xfails, 'YELLOW', 'NEW XFAIL: {}')
    sect("Fixes (failed→passed)", fixes, 'GREEN', 'FIXED: {}')
    sect("Resolved XFails", resolved_xfails, 'GREEN', 'RESOLVED XFAIL: {}')
    sect("Added Passing Tests", added_pass, 'GREEN', 'ADDED PASS: {}')
    sect("Removed Tests", removed, 'YELLOW', 'REMOVED: {}')
    sect("Persistent Failures", persistent_fail, 'YELLOW', 'PERSIST FAIL: {}')
    if persistent_pass:
        total_pp = len(persistent_pass)
        pass_limit = total_pp if show_all else 10
        heading = f"Total persistent passes: {total_pp} (showing {'all' if show_all else f'first {pass_limit}'})"
        print(pal.c('CYAN', heading))
        for t in persistent_pass[:pass_limit]:
            print(pal.c('CYAN', f"  PERSIST PASS: {disamb(t)}"))
        if not show_all and total_pp > pass_limit:
            print(pal.c('CYAN', f"  … ({total_pp-pass_limit} more passes suppressed; use --all to show)"))
    else:
        print(pal.c('CYAN', 'Total persistent passes: 0'))

    print()
    # Performance sections if requested
    if perf:
        if slower:
            print(pal.c('YELLOW', f"Slower Tests: {len(slower)} (ratio>={perf_ratio} & +{perf_abs:.3f}s)"))
            for tid, o, n, r, d in slower[:20]:
                print(pal.c('YELLOW', f"  SLOWER: {disamb(tid)} +{d:.3f}s x{r:.2f} ({o:.3f}s -> {n:.3f}s)"))
            if len(slower) > 20:
                print(pal.c('YELLOW', f"  … ({len(slower)-20} more)"))
        if perf_show_faster and faster:
            print(pal.c('GREEN', f"Faster Tests: {len(faster)} (ratio>={perf_ratio} & -{perf_abs:.3f}s)"))
            for tid, o, n, r, d in faster[:20]:
                print(pal.c('GREEN', f"  FASTER: {disamb(tid)} -{d:.3f}s x{r:.2f} ({o:.3f}s -> {n:.3f}s)"))
            if len(faster) > 20:
                print(pal.c('GREEN', f"  … ({len(faster)-20} more)"))
        if not slower and (not faster or not perf_show_faster):
            print(pal.c('YELLOW', f"Slower Tests: 0 (no test exceeded ratio>={perf_ratio} and +{perf_abs:.3f}s)"))
            # Provide top 3 near misses for context
            near = []
            for tid in sorted(set(ia) & set(ib)):
                o = ia[tid].get('duration'); n = ib[tid].get('duration')
                if isinstance(o,(int,float)) and isinstance(n,(int,float)) and n>o:
                    near.append((n-o, (n/(o or 1e-9)), tid, o, n))
            near.sort(reverse=True)
            if near:
                for delta, ratio, tid, o, n in near[:3]:
                    print(pal.c('YELLOW', f"  NEAR: {disamb(tid)} +{delta:.3f}s x{ratio:.2f} ({o:.3f}s -> {n:.3f}s)"))
            else:
                print(pal.c('YELLOW', "  (no increases at all)"))

    metrics = [
        ("new_pass", len(added_pass)),
        ("new_fail", len(added_fail)),
        ("fixes", len(fixes)),
        ("regressions", len(regressions)),
        ("removed", len(removed)),
        ("new_xfails", len(new_xfails)),
        ("resolved_xfails", len(resolved_xfails)),
        ("persistent_fail", len(persistent_fail)),
        ("persistent_pass", len(persistent_pass)),
    ]
    if perf:
        metrics.append(("slower", len(slower)))
    metrics.append(("total_changed", total_changed))

    width = max(len(k) for k,_ in metrics)
    def colorize(name: str, val: int) -> str:
        if val == 0:
            return str(val)
        if name in {"new_fail", "regressions"}:
            return pal.c('RED', str(val))
        if name in {"fixes", "new_pass", "resolved_xfails"}:
            return pal.c('GREEN', str(val))
        if name in {"new_xfails", "persistent_fail", "slower"}:
            return pal.c('YELLOW', str(val))
        return pal.c('CYAN', str(val))

    print(pal.c('BOLD', 'Summary Metrics:'))
    for k,v in metrics:
        print(f"  {k.ljust(width)} : {colorize(k,v)}")
    return 0


if __name__ == '__main__':
    args_plain = False
    full_ids = False
    show_all = False
    perf = False
    perf_ratio = 1.3
    perf_abs = 0.05
    perf_show_faster = False
    raw_paths = []
    it = iter(sys.argv[1:])
    for tok in it:
        if tok in {'--plain','--no-color'}:
            args_plain = True
        elif tok == '--full-ids':
            full_ids = True
        elif tok == '--all':
            show_all = True
        elif tok == '--perf':
            perf = True
        elif tok == '--perf-show-faster':
            perf = True; perf_show_faster = True
        elif tok == '--perf-ratio':
            try:
                perf_ratio = float(next(it))
            except (StopIteration, ValueError):
                print('--perf-ratio requires a float', file=sys.stderr); sys.exit(2)
            perf = True
        elif tok == '--perf-abs':
            try:
                perf_abs = float(next(it))
            except (StopIteration, ValueError):
                print('--perf-abs requires a float', file=sys.stderr); sys.exit(2)
            perf = True
        elif tok.startswith('-'):
            print(f'Unknown flag {tok}', file=sys.stderr)
            sys.exit(2)
        else:
            raw_paths.append(tok)
    if len(raw_paths) != 2:
        print('Usage: compare_snapshots.py [--plain|--no-color] [--full-ids] [--all] [--perf [--perf-ratio R] [--perf-abs S] [--perf-show-faster]] <snapshot_a.json> <snapshot_b.json>', file=sys.stderr)
        sys.exit(2)
    sys.exit(main(raw_paths[0], raw_paths[1], plain=args_plain, show_all=show_all, full_ids=full_ids,
                 perf=perf, perf_ratio=perf_ratio, perf_abs=perf_abs, perf_show_faster=perf_show_faster))
