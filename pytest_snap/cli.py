from __future__ import annotations

"""Primary CLI (migrated). See README for usage examples."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import datetime
from pathlib import Path
from typing import List, Sequence


def _load_json(path: Path):
	with path.open('r', encoding='utf-8') as f:
		return json.load(f)


def _supports_color(disable: bool) -> bool:
	if disable:
		return False
	if os.environ.get('NO_COLOR') is not None:
		return False
	return sys.stdout.isatty()


class _Palette:
	def __init__(self, enabled: bool):
		if not enabled:
			for k in ["RESET","GREEN","RED","YELLOW","CYAN","BOLD"]:
				setattr(self, k, '')
		else:
			self.RESET='\x1b[0m'; self.GREEN='\x1b[32m'; self.RED='\x1b[31m'; self.YELLOW='\x1b[33m'; self.CYAN='\x1b[36m'; self.BOLD='\x1b[1m'

	def c(self, color: str, text: str) -> str:
		v = getattr(self, color, '')
		return f"{v}{text}{self.RESET}" if v else text


def diff_snapshots(a_path: Path, b_path: Path, *, plain=False, show_all=False, full_ids=False,
			   perf=False, perf_ratio=1.3, perf_abs=0.05, perf_show_faster=False) -> int:
	"""Diff two snapshot JSON files.

	Supports both the legacy/expanded schema (with top-level 'tests' entries containing
	'id','outcome','duration') and the current minimal 0.1.0 plugin schema which emits
	'results' entries containing 'nodeid','outcome','dur_ns'. This function normalizes
	both forms into a common structure so counts like persistent_pass work regardless
	of which producer created the snapshots.
	"""
	A = _load_json(a_path); B = _load_json(b_path)
	pal = _Palette(_supports_color(plain) )

	def _extract_tests(s: dict):
		# Preferred rich schema
		if 'tests' in s:
			out=[]
			for t in s.get('tests', []):
				if not isinstance(t, dict):
					continue
				out.append({
					'id': t.get('id'),
					'outcome': t.get('outcome'),
					'duration': t.get('duration') if isinstance(t.get('duration'), (int,float)) else None,
				})
			return out
		# Minimal plugin schema (0.1.0): 'results' with nodeid/dur_ns
		if 'results' in s:
			out=[]
			for r in s.get('results', []):
				if not isinstance(r, dict):
					continue
				dur_ns = r.get('dur_ns')
				duration = (dur_ns / 1e9) if isinstance(dur_ns, (int, float)) else None
				out.append({
					'id': r.get('nodeid'),
					'outcome': r.get('outcome'),
					'duration': duration,
				})
			return out
		return []

	def idx(s: dict):
		return {t['id']: t for t in _extract_tests(s) if t.get('id')}

	ia, ib = idx(A), idx(B)

	regressions=fixes=persistent_fail=persistent_pass=added_pass=added_fail=removed=new_xfails=resolved_xfails=persistent_xfails=xpassed=None  # type: ignore
	regressions=[]; fixes=[]; persistent_fail=[]; persistent_pass=[]; added_pass=[]; added_fail=[]; removed=[]; new_xfails=[]; resolved_xfails=[]; persistent_xfails=[]; xpassed=[]

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
		if prev_out in {'xfailed','xfail'} and cur_out in {'passed','xpassed'}:
			resolved_xfails.append(tid)
		if prev_out not in {'xfailed','xfail'} and cur_out in {'xfailed','xfail'}:
			new_xfails.append(tid)
		if prev_out in {'xfailed','xfail'} and cur_out in {'xfailed','xfail'}:
			persistent_xfails.append(tid)
		if cur_out in {'xpassed','xpass'}:
			xpassed.append(tid)

	for tid, rec in ib.items():
		if tid in ia:
			continue
		if rec.get('outcome') == 'failed':
			added_fail.append(tid)
		else:
			added_pass.append(tid)
		if rec.get('outcome') in {'xfailed','xfail'}:
			new_xfails.append(tid)

	slower=[]; faster=[]
	if perf:
		for tid in sorted(set(ia) & set(ib)):
			o = ia[tid].get('duration'); n = ib[tid].get('duration')
			if isinstance(o,(int,float)) and isinstance(n,(int,float)):
				if n > o and (n/(o or 1e-9)) >= perf_ratio and (n-o) >= perf_abs:
					slower.append((tid,o,n,n/(o or 1e-9), n-o))
				elif perf_show_faster and o>n and (o/(n or 1e-9)) >= perf_ratio and (o-n) >= perf_abs:
					faster.append((tid,o,n,o/(n or 1e-9), o-n))

	total_changed = sum(map(len, [fixes, regressions, added_pass, added_fail, removed, new_xfails, resolved_xfails]))
	header = f"SNAPSHOT DIFF {a_path.name} -> {b_path.name}"
	print(pal.c('BOLD', pal.c('CYAN', header)))
	print(pal.c('CYAN', '-' * len(header)))

	def short(tid: str) -> str:
		if full_ids: return tid
		return tid.split('::')[-1]

	if not full_ids:
		counts={}
		for coll in [regressions, fixes, persistent_fail, persistent_pass, added_pass, added_fail, removed, new_xfails, resolved_xfails]:
			for entry in coll:
				tid = entry[0] if isinstance(entry, tuple) else entry
				s=short(tid); counts[s]=counts.get(s,0)+1
		def disamb(tid: str) -> str:  # type: ignore
			s=short(tid)
			if counts.get(s,0)>1:
				stem = tid.split('::')[0].rsplit('/',1)[-1]
				return f"{stem}::{s}"
			return s
	else:
		def disamb(tid: str) -> str:  # type: ignore
			return tid

	def sect(title, items, color, label_fmt, limit=20):
		if not items: return
		print(pal.c(color, f"{title}: {len(items)}"))
		for t in items[:limit]:
			if isinstance(t, tuple):
				tid, extra = t
				label = label_fmt.format(f"{disamb(tid)} ({extra})")
			else:
				label = label_fmt.format(disamb(t))
			print(pal.c(color, f"  {label}"))
		if len(items) > limit:
			print(pal.c(color, f"  … ({len(items)-limit} more)"))

	sect("Regressions (passed→failed)", regressions, 'RED', 'REGRESSED: {}')
	sect("Added Failing Tests", added_fail, 'RED', 'ADDED FAIL: {}')
	sect("New XFails", new_xfails, 'YELLOW', 'NEW XFAIL: {}')
	sect("Fixes (failed→passed)", fixes, 'GREEN', 'FIXED: {}')
	sect("Resolved XFails", resolved_xfails, 'GREEN', 'RESOLVED XFAIL: {}')
	sect("Added Passing Tests", added_pass, 'GREEN', 'ADDED PASS: {}')
	sect("Removed Tests", removed, 'YELLOW', 'REMOVED: {}')
	sect("Persistent Failures", persistent_fail, 'YELLOW', 'PERSIST FAIL: {}')
	sect("Persistent XFails", persistent_xfails, 'YELLOW', 'PERSIST XFAIL: {}')
	sect("XPASS (unexpected passes)", xpassed, 'GREEN', 'XPASS: {}')
	if persistent_pass:
		tot=len(persistent_pass); lim = tot if show_all else 10
		heading = f"Total persistent passes: {tot} (showing {'all' if show_all else f'first {lim}'})"
		print(pal.c('CYAN', heading))
		for t in persistent_pass[:lim]:
			print(pal.c('CYAN', f"  PERSIST PASS: {disamb(t)}"))
		if not show_all and tot>lim:
			print(pal.c('CYAN', f"  … ({tot-lim} more passes suppressed; use --all to show)"))
	else:
		print(pal.c('CYAN', 'Total persistent passes: 0'))

	print()
	if perf:
		if slower:
			print(pal.c('YELLOW', f"Slower Tests: {len(slower)} (ratio>={perf_ratio} & +{perf_abs:.3f}s)"))
			for tid,o,n,r,d in slower[:20]:
				print(pal.c('YELLOW', f"  SLOWER: {disamb(tid)} +{d:.3f}s x{r:.2f} ({o:.3f}s -> {n:.3f}s)"))
			if len(slower)>20:
				print(pal.c('YELLOW', f"  … ({len(slower)-20} more)"))
		if perf_show_faster and faster:
			print(pal.c('GREEN', f"Faster Tests: {len(faster)} (ratio>={perf_ratio} & -{perf_abs:.3f}s)"))
			for tid,o,n,r,d in faster[:20]:
				print(pal.c('GREEN', f"  FASTER: {disamb(tid)} -{d:.3f}s x{r:.2f} ({o:.3f}s -> {n:.3f}s)"))
			if len(faster)>20:
				print(pal.c('GREEN', f"  … ({len(faster)-20} more)"))
		if not slower and (not faster or not perf_show_faster):
			print(pal.c('YELLOW', f"Slower Tests: 0 (no test exceeded ratio>={perf_ratio} and +{perf_abs:.3f}s)"))
	metrics=[
		("new_pass", len(added_pass)), ("new_fail", len(added_fail)), ("fixes", len(fixes)),
		("regressions", len(regressions)), ("removed", len(removed)), ("new_xfails", len(new_xfails)),
		("resolved_xfails", len(resolved_xfails)), ("persistent_xfails", len(persistent_xfails)),
		("xpassed", len(xpassed)), ("persistent_fail", len(persistent_fail)), ("persistent_pass", len(persistent_pass)),
	]
	if perf: metrics.append(("slower", len(slower)))
	metrics.append(("total_changed", total_changed))
	width = max(len(k) for k,_ in metrics)
	def colorize(metric_name: str, metric_val: int) -> str:
		if metric_val == 0:
			return str(metric_val)
		if metric_name in {"new_fail","regressions"}:
			return pal.c('RED', str(metric_val))
		if metric_name in {"fixes","new_pass","resolved_xfails","xpassed"}:
			return pal.c('GREEN', str(metric_val))
		if metric_name in {"new_xfails","persistent_fail","persistent_xfails","slower"}:
			return pal.c('YELLOW', str(metric_val))
		return pal.c('CYAN', str(metric_val))
	print(pal.c('BOLD', 'Summary Metrics:'))
	for k,v in metrics:
		print(f"  {k.ljust(width)} : {colorize(k,v)}")
	return 0


def code_version_diff(old: Path, new: Path, *, limit: int = 20, no_color: bool = False) -> int:
	import ast, difflib, re, textwrap
	ANSI={'red':'\x1b[31m','green':'\x1b[32m','yellow':'\x1b[33m','magenta':'\x1b[35m','cyan':'\x1b[36m','bold':'\x1b[1m','dim':'\x1b[2m','reset':'\x1b[0m'}
	def C(color: str, txt: str):
		if no_color or not sys.stdout.isatty(): return txt
		return f"{ANSI.get(color,'')}{txt}{ANSI['reset']}"
	class TestFunc:  # minimal
		def __init__(self, file: Path, name: str, qual: str, source: List[str]): self.file=file; self.name=name; self.qual=qual; self.source=source
	def extract(path: Path):
		code=path.read_text().splitlines(keepends=True)
		try: tree=ast.parse(''.join(code))
		except SyntaxError: return {}
		out={}
		for node in tree.body:
			if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
				start=node.lineno-1; end=getattr(node,'end_lineno', None)
				if end is None:
					end=start+1
					while end < len(code) and not code[end].startswith('def '): end+=1
				src=code[start:end]
				qual=f"{path.name}::{node.name}"; out[qual]=TestFunc(path,node.name,qual,src)
		return out
	def collect(dir_path: Path):
		agg={}
		for p in sorted(dir_path.glob('test_*.py')): agg.update(extract(p))
		return agg
	if not old.is_dir() or not new.is_dir():
		print('Both paths must be directories', file=sys.stderr); return 2
	A=collect(old); B=collect(new)
	ka=set(A); kb=set(B)
	added=sorted(kb-ka); removed=sorted(ka-kb); common=sorted(ka & kb)
	modified=[]
	for k in common:
		if A[k].source != B[k].source: modified.append((k,A[k],B[k]))
	def u_diff(a: List[str], b: List[str]):
		out=[]
		for line in difflib.unified_diff(a,b,fromfile='a',tofile='b',n=3):
			if line.startswith('---') or line.startswith('+++'): continue
			if line.startswith('@@'): out.append(C('magenta', line.rstrip()))
			elif line.startswith('+'): out.append(C('green', line.rstrip()))
			elif line.startswith('-'): out.append(C('red', line.rstrip()))
			else: out.append(C('dim', line.rstrip()))
		return out
	R_RANGE=re.compile(r"range\((\d+)\)"); R_SLEEP=re.compile(r"time\.sleep\((\d+\.?\d*)\)")
	def perf_hints(old_src: List[str], new_src: List[str]):
		hints=[]
		o_r=list(map(int,R_RANGE.findall(''.join(old_src)))); n_r=list(map(int,R_RANGE.findall(''.join(new_src))))
		if o_r and n_r and sum(n_r) > sum(o_r):
			ratio=sum(n_r)/max(1,sum(o_r)); hints.append(f"range workload ↑ x{ratio:.2f} ({sum(o_r)}→{sum(n_r)})")
		o_s=[float(x) for x in R_SLEEP.findall(''.join(old_src))]; n_s=[float(x) for x in R_SLEEP.findall(''.join(new_src))]
		if o_s and n_s and sum(n_s) > sum(o_s):
			delta=sum(n_s)-sum(o_s); hints.append(f"sleep total ↑ +{delta:.3f}s ({sum(o_s):.3f}→{sum(n_s):.3f})")
		return hints
	print(C('bold', f"Code Version Diff: {old.name} → {new.name}"))
	print(f"Tests: {len(A)} → {len(B)} | added {len(added)} removed {len(removed)} modified {len(modified)}")
	def list_block(lst, color):
		if not lst: print(C(color,'  (none)')); return
		for x in lst: print(C(color, f"  - {x}"))
	print('\n'+C('green','Added Tests:')); list_block(added,'green')
	print('\n'+C('red','Removed Tests:')); list_block(removed,'red')
	print('\n'+C('yellow','Modified Tests:'))
	if not modified: print(C('yellow','  (none)'))
	else:
		for idx,(qual,old_f,new_f) in enumerate(modified):
			if idx >= limit: print(f"  ... ({len(modified)-limit} more omitted)"); break
			hints=perf_hints(old_f.source,new_f.source); hint_txt=(' '+', '.join(hints)) if hints else ''
			print(C('bold', f"  * {qual}{hint_txt}"))
			for line in u_diff(old_f.source,new_f.source): print('    '+line)
	print()
	return 0


def run_tests(label: str, *, tests_dir: Path, artifacts: Path, html: bool, history: bool, extra_pytest: Sequence[str]) -> int:
	"""Invoke pytest to produce a snapshot using the new minimal plugin.

	NOTE: Legacy flags like --snap-save-baseline / --snap-history-path were
	removed; we now rely solely on `--snap` + `--snap-out`.
	The `history` flag is currently ignored (reserved for future use).
	"""
	artifacts.mkdir(parents=True, exist_ok=True)
	snap = artifacts / f"snap_{label}.json"
	html_path = artifacts / f"run_{label}.html"
	cmd = [
		sys.executable,
		'-m', 'pytest',
		str(tests_dir),
		'--snap',
		'--snap-out', str(snap),
	]
	# If using example suite directories, override root pytest.ini (which pins testpaths=tests)
	if 'example_suite' in str(tests_dir):
		empty_cfg = artifacts / 'pytest_empty.ini'
		if not empty_cfg.exists():
			empty_cfg.write_text('[pytest]\n', encoding='utf-8')
		cmd.insert(cmd.index('-m') + 2, '-c')  # insert after '-m', 'pytest'
		cmd.insert(cmd.index('-c') + 1, str(empty_cfg))
	# Forward extra pytest args as-is
	extra_clean = list(extra_pytest)
	if html:
		# Optional dependency; keep old behavior if user has pytest-html installed
		cmd += ['--html', str(html_path), '--self-contained-html']
	# history placeholder intentionally not implemented in minimal plugin
	cmd += list(extra_clean)
	print("== RUN", label, '==')
	print(' '.join(cmd))
	rc = subprocess.call(cmd)
	if not snap.exists():
		print(f"Snapshot not created: {snap}", file=sys.stderr)
		return rc or 1
	print(f"Saved snapshot: {snap}")
	if html and html_path.exists():
		print(f"HTML report: {html_path}")
	return rc


def discover_tests_dir(explicit: str | None) -> Path:
	if explicit:
		return Path(explicit)
	# Default priority now prefers root tests; example suite handled via --example-suite flag elsewhere
	if Path('tests').is_dir():
		return Path('tests')
	if Path('example_suite/tests').is_dir():
		return Path('example_suite/tests')
	return Path('.')


def main(argv: Sequence[str] | None = None) -> int:
	argv = list(argv or sys.argv[1:])
	ap = argparse.ArgumentParser(
		prog='pytest-snap',
		description=(
			'High-level workflow helper for pytest-snap. Labels name snapshot files; test discovery defaults to ./tests unless --tests is provided. '\
			"For source changes use 'pytest-snap diff <A> <B> --code' to compare version directories under --versions-base. "\
			"See README or 'pytest-snap perf' for performance flags."
		),
		epilog=(
			"Examples:\n"
			"  pytest-snap run v1                    # runs ./tests, writes .artifacts/snap_v1.json\n"
			"  pytest-snap run v1 --tests tests/api  # target a specific folder/file/node\n"
			"  pytest-snap diff v1 v2 --code         # code diff looks in --versions-base/<A>,<B> (default .)\n"
			"  pytest-snap diff v1 v2 --perf         # slower test analysis\n"
			"  pytest-snap diff v1 v2 --code --perf  # combine both analyses\n"
		),
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	sub = ap.add_subparsers(dest='cmd', required=True)

	ap_run = sub.add_parser('run', help='Run tests and write labeled snapshot (.artifacts/snap_<label>.json)')
	ap_run.add_argument('label', help='Arbitrary label; names the output snapshot file (e.g., snap_<label>.json)')
	ap_run.add_argument('--tests', help='Tests directory/file/node to run (default: ./tests if present, else auto)')
	ap_run.add_argument('--artifacts', default='.artifacts', help='Artifacts directory (default: .artifacts); writes snap_<label>.json')
	ap_run.add_argument('--html', action='store_true', help='Generate pytest-html report (opt-in)')
	ap_run.add_argument('--no-history', action='store_true', help='Disable flake history recording')

	ap_all = sub.add_parser('all', help='Run multiple labels sequentially (default: v1 v2 v3)')
	ap_all.add_argument('labels', nargs='*')
	ap_all.add_argument('--tests', help='Tests directory/file/node to run for each label (default: ./tests if present, else auto)')
	ap_all.add_argument('--artifacts', default='.artifacts', help='Artifacts directory (default: .artifacts)')
	ap_all.add_argument('--html', action='store_true', help='Generate pytest-html reports for each run')
	ap_all.add_argument('--no-history', action='store_true')

	ap_diff = sub.add_parser('diff', help='Diff two labeled snapshots (A -> B). Labels map to .artifacts/snap_<label>.json')
	ap_perf = sub.add_parser('perf', help='Show performance diff usage (shortcut docs for diff --perf)')
	ap_timeline = sub.add_parser('timeline', help='Show chronological snapshot summary (optionally since a commit)')
	ap_timeline.add_argument('--artifacts', default='.artifacts')
	ap_timeline.add_argument('--since', help='Git commit hash (short) to start from')
	ap_timeline.add_argument('--limit', type=int, default=0, help='Max snapshots to display (0 = all)')
	ap_timeline.add_argument('--json', action='store_true', help='Emit machine-readable JSON array')
	ap_diff.add_argument('a'); ap_diff.add_argument('b')
	ap_diff.add_argument('--artifacts', default='.artifacts', help='Artifacts directory to read snapshots from (default: .artifacts)')
	ap_diff.add_argument('--plain', action='store_true')
	ap_diff.add_argument('--full-ids', action='store_true')
	ap_diff.add_argument('--all', dest='show_all', action='store_true')
	ap_diff.add_argument('--perf', action='store_true')
	ap_diff.add_argument('--perf-ratio', type=float, default=1.3)
	ap_diff.add_argument('--perf-abs', type=float, default=0.05)
	ap_diff.add_argument('--perf-show-faster', action='store_true')
	ap_diff.add_argument('--code', action='store_true', help='Also show code-level diff; searches <A>,<B> under --versions-base')
	ap_diff.add_argument('--code-only', action='store_true', help='Only show code-level diff (suppress snapshot outcomes)')
	ap_diff.add_argument('--versions-base', default='.', help='Directory containing version subfolders (default .). Used by --code to locate <A> and <B>')

	ap_list = sub.add_parser('list', help='List available snapshots')
	ap_list.add_argument('--artifacts', default='.artifacts')

	ap_clean = sub.add_parser('clean', help='Remove artifacts directory')
	ap_clean.add_argument('--artifacts', default='.artifacts')

	ap_show = sub.add_parser('show', help='Display summary of a single snapshot (no test run)')
	ap_show.add_argument('label')
	ap_show.add_argument('--artifacts', default='.artifacts')
	ap_show.add_argument('--plain', action='store_true')
	ap_show.add_argument('--top-slowest', type=int, default=10, help='Show N slowest tests (default 10)')
	ap_show.add_argument('--full', action='store_true', help='List all failed/xfail tests (not truncated)')
	ap_show.add_argument('--max-id-len', type=int, default=90, help='Max length of displayed test id (default 90)')
	ap_show.add_argument('--no-trunc', action='store_true', help='Disable test id truncation')
	ap_show.add_argument('--full-ids', action='store_true', help='Show full path test ids instead of shortened form')

	# Parse known args; anything unrecognized we treat as extra pytest args
	args, extra_args = ap.parse_known_args(argv)

	if args.cmd == 'run':
		# Determine tests directory precedence: explicit --tests > auto-discover
		if getattr(args, 'tests', None):
			tests_dir = discover_tests_dir(args.tests)
		else:
			tests_dir = discover_tests_dir(None)
		# Debug trace to diagnose unexpected directory selection
		if os.environ.get('PYTEST_SNAP_DEBUG'):
			print(f"[pytest-snap] selected tests_dir={tests_dir}")
		if not tests_dir.exists():
			print(f"Tests directory not found: {tests_dir}", file=sys.stderr)
			return 2
		return run_tests(args.label, tests_dir=tests_dir, artifacts=Path(args.artifacts), html=args.html, history=not args.no_history, extra_pytest=extra_args)

	if args.cmd == 'all':
		labels = args.labels or ['v1','v2','v3']
		rc = 0
		for lbl in labels:
			if getattr(args, 'tests', None):
				this_dir = discover_tests_dir(args.tests)
			else:
				this_dir = discover_tests_dir(None)
			if not this_dir.exists():
				print(f"Tests directory not found for {lbl}: {this_dir}", file=sys.stderr)
				rc = 2
				continue
			r = run_tests(lbl, tests_dir=this_dir, artifacts=Path(args.artifacts), html=args.html, history=not args.no_history, extra_pytest=extra_args)
			rc = r or rc
		return rc

	if args.cmd == 'diff':
		art = Path(args.artifacts)
		a_file = art / f"snap_{args.a}.json"; b_file = art / f"snap_{args.b}.json"
		if not a_file.exists() or not b_file.exists():
			print(f"Missing snapshots: {a_file if not a_file.exists() else ''} {b_file if not b_file.exists() else ''}", file=sys.stderr)
			return 2
		if not args.code_only:
			diff_snapshots(a_file, b_file, plain=args.plain, show_all=args.show_all, full_ids=args.full_ids,
					   perf=args.perf, perf_ratio=args.perf_ratio, perf_abs=args.perf_abs, perf_show_faster=args.perf_show_faster)
		# Determine if we should perform code diff
		do_code = args.code or args.code_only
		if do_code:
			base = Path(args.versions_base)
			old_dir = base / args.a; new_dir = base / args.b
			if not (old_dir.is_dir() and new_dir.is_dir()):
				# fallback attempt to example_suite/<label> dirs if present
				alt_base = Path('example_suite')
				alt_old, alt_new = alt_base / args.a, alt_base / args.b
				if alt_old.is_dir() and alt_new.is_dir():
					base = alt_base; old_dir, new_dir = alt_old, alt_new
			if old_dir.is_dir() and new_dir.is_dir():
				print("\n== CODE DIFF ==")
				print(f"(using versions base: {base})")
				code_version_diff(old_dir, new_dir)
			else:
				print(f"(code diff skipped: missing {old_dir} or {new_dir}; specify --versions-base <dir>)", file=sys.stderr)
		return 0

	if args.cmd == 'perf':
		print("Performance Diff Usage:\n")
		print("  pytest-snap diff <A> <B> --perf [--perf-ratio R] [--perf-abs S] [--perf-show-faster]\n")
		print("Flags:")
		print("  --perf               Enable slower test detection output")
		print("  --perf-ratio R       Require at least Rx slowdown (default 1.30)")
		print("  --perf-abs S         Require at least S seconds added (default 0.05)")
		print("  --perf-show-faster   Also list significantly faster tests")
		print("\nA test is reported as slower only if BOTH thresholds are exceeded.")
		print("For gating during runs use: --snap-fail-on slower --snap-slower-threshold-ratio ...")
		print("See README.md Performance sections for deeper explanation.")
		return 0

	if args.cmd == 'timeline':
		art = Path(args.artifacts)
		if not art.exists():
			print('(no artifacts directory)'); return 0
		snaps = sorted(art.glob('snap_*.json'))
		if not snaps:
			print('(no snapshots found)'); return 0
		records = []
		def load(p: Path):
			try:
				return json.load(p.open('r', encoding='utf-8'))
			except Exception:
				return None
		for p in snaps:
			data = load(p)
			if not data: continue
			created = data.get('created_at') or ''
			commit = data.get('git_commit', 'unknown')
			tests = data.get('tests', [])
			outcomes = {t.get('id'): t.get('outcome') for t in tests}
			counts = {
				'total': len(tests),
				'failed': sum(1 for o in outcomes.values() if o == 'failed'),
				'passed': sum(1 for o in outcomes.values() if o == 'passed'),
				'xfailed': sum(1 for o in outcomes.values() if o in {'xfailed','xfail'}),
				'xpassed': sum(1 for o in outcomes.values() if o in {'xpassed','xpass'}),
			}
			label = p.stem.replace('snap_','',1)
			records.append({'file': p.name, 'label': label, 'created_at': created, 'git_commit': commit, **counts, 'outcomes': outcomes})
		def parse_ts(s: str):
			try:
				return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ')
			except Exception:
				return datetime.datetime.fromtimestamp(0)
		records.sort(key=lambda r: (parse_ts(r['created_at']), r['label']))
		start_idx = 0
		if args.since:
			for i,r in enumerate(records):
				if r.get('git_commit') == args.since:
					start_idx = i; break
			else:
				print(f"(commit {args.since} not found; showing all)")
		view = records[start_idx:]
		timeline = []
		prev = None
		for r in view:
			outcomes = r.pop('outcomes')
			delta = {'new_fail':0,'fixes':0,'regressions':0}
			if prev:
				for tid,out in outcomes.items():
					po = prev['__outcomes'].get(tid)
					if po != 'failed' and out == 'failed':
						delta['new_fail'] += 1
					if po == 'failed' and out == 'passed':
						delta['fixes'] += 1
					if po == 'passed' and out == 'failed':
						delta['regressions'] += 1
			entry = {k:v for k,v in r.items() if k != '__outcomes'}
			entry.update(delta)
			timeline.append(entry)
			r['__outcomes'] = outcomes
			prev = r
		if args.limit > 0:
			timeline = timeline[-args.limit:]
		if args.json:
			print(json.dumps(timeline, separators=(',',':')))
			return 0
		print(f"TIMELINE ({len(timeline)} snapshots)")
		for t in timeline:
			print(f"{t['created_at'] or '?'} {t['label']} commit={t['git_commit']} total={t['total']} fail={t['failed']} new_fail={t['new_fail']} fixes={t['fixes']} regressions={t['regressions']}")
		return 0

	if args.cmd == 'list':
		art = Path(args.artifacts)
		if not art.exists():
			print('(no artifacts directory)'); return 0
		snaps = sorted(art.glob('snap_*.json'))
		if not snaps:
			print('(no snapshots found)'); return 0
		for s in snaps: print(s.name)
		return 0

	if args.cmd == 'clean':
		art = Path(args.artifacts)
		if art.exists():
			shutil.rmtree(art); print(f"Removed {art}")
		else:
			print(f"No artifacts directory to remove ({art})")
		return 0

	if args.cmd == 'show':
		art = Path(args.artifacts)
		snap = art / f"snap_{args.label}.json"
		if not snap.exists():
			print(f"Snapshot not found: {snap}", file=sys.stderr)
			return 2
		data = _load_json(snap)
		pal = _Palette(_supports_color(args.plain))
		tests = data.get('tests', [])
		total = len(tests)
		counts = {'passed': 0, 'failed': 0, 'xfailed': 0, 'xpassed': 0, 'skipped': 0, 'other': 0}
		for t in tests:
			o = t.get('outcome')
			if o in counts: counts[o] += 1
			else: counts['other'] += 1
		header = f"SNAPSHOT {snap.name} (total {total})"
		print(pal.c('BOLD', pal.c('CYAN', header)))
		passed = counts['passed']; failed = counts['failed']; xfailed = counts['xfailed']; xpassed = counts['xpassed']; skipped = counts['skipped']
		print(f"  passed={passed} failed={failed} xfailed={xfailed} xpassed={xpassed} skipped={skipped} other={counts['other']}")
		fails = [t for t in tests if t.get('outcome') == 'failed']
		xfs = [t for t in tests if t.get('outcome') == 'xfailed']
		xps = [t for t in tests if t.get('outcome') == 'xpassed']
		passes = [t for t in tests if t.get('outcome') == 'passed']
		def _shorten(s: str) -> str:
			if args.full_ids: return s
			if '::' in s:
				file_part, rest = s.split('::', 1)
				base = Path(file_part).name
				if base.endswith('.py'): base = base[:-3]
				return f"{base}::{rest}"
			return Path(s).name
		def _truncate(s: str) -> str:
			if args.no_trunc: return s
			max_len = max(10, args.max_id_len)
			if len(s) <= max_len: return s
			head = int(max_len * 0.6); tail = max_len - head - 1
			return f"{s[:head]}…{s[-tail:]}"
		def list_block(title, bucket, color, limit=10):
			if not bucket: return
			print(pal.c(color, f"{title}: {len(bucket)}"))
			cap = bucket if args.full else bucket[:limit]
			for t in cap:
				disp = _shorten(t['id']); disp = _truncate(disp)
				print(pal.c(color, f"  - {disp}"))
			if not args.full and len(bucket) > limit:
				print(pal.c(color, f"  … ({len(bucket) - limit} more; use --full)"))
		list_block('Failures', fails, 'RED')
		list_block('XFails', xfs, 'YELLOW')
		list_block('XPASS', xps, 'GREEN')
		list_block('Passes', passes, 'GREEN', limit=20)
		with_dur = [t for t in tests if isinstance(t.get('duration'), (int, float))]
		with_dur.sort(key=lambda t: t.get('duration') or 0, reverse=True)
		if with_dur:
			top_n = min(args.top_slowest, len(with_dur))
			print(pal.c('CYAN', f"Slowest {top_n} tests:"))
			for t in with_dur[:args.top_slowest]:
				disp = _shorten(t['id']); disp = _truncate(disp)
				print(pal.c('CYAN', f"  {t['duration']:.4f}s {disp}"))
		return 0

	return 1


def main_cli():  # convenience for entry point adaptation if ever needed
	return main()


if __name__ == '__main__':  # pragma: no cover
	raise SystemExit(main())

__all__ = ["main"]
