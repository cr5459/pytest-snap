"""Benchmark diff performance and rudimentary memory usage."""
from __future__ import annotations

import argparse
import json
import time

try:  # pragma: no cover
    import psutil
except Exception:  # pragma: no cover
    psutil = None

from pytest_html_baseline.diff import diff_snapshots


def load(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline")
    ap.add_argument("current")
    ap.add_argument("--ratio", type=float, default=1.3)
    ap.add_argument("--abs", dest="abs_thr", type=float, default=0.2)
    args = ap.parse_args()

    b = load(args.baseline)
    c = load(args.current)

    if psutil:
        process = psutil.Process()
        rss_before = process.memory_info().rss
    else:
        rss_before = 0
    t0 = time.perf_counter()
    d = diff_snapshots(b, c, slower_ratio=args.ratio, slower_abs=args.abs_thr)
    dt = (time.perf_counter() - t0) * 1000
    if psutil:
        rss_after = process.memory_info().rss
        rss_delta = rss_after - rss_before
    else:
        rss_delta = 0
    print(
        json.dumps(
            {
                "time_ms": round(dt, 2),
                "n_baseline": len(b.get("tests", [])),
                "n_current": len(c.get("tests", [])),
                "rss_delta": rss_delta,
                "summary": d["summary"],
            }
        )
    )


if __name__ == "__main__":  # pragma: no cover
    main()
