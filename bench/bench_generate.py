"""Generate synthetic snapshot JSON files for benchmarking."""
from __future__ import annotations

import json
import random
import argparse
from datetime import datetime, timezone


def gen_snapshot(n: int, fail_rate: float, seed: int, slow_bias: float):
    rnd = random.Random(seed)
    tests = []
    for i in range(n):
        outcome = "failed" if rnd.random() < fail_rate else "passed"
        dur = rnd.random() * 0.5 * slow_bias
        tests.append({"id": f"t::{i}", "outcome": outcome, "duration": round(dur, 6)})
    return {
        "version": 1,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "collected": n,
        "tests": tests,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("-n", type=int, default=50000)
    ap.add_argument("--fail-rate", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--slow-bias", type=float, default=1.0)
    args = ap.parse_args()
    snap = gen_snapshot(args.n, args.fail_rate, args.seed, args.slow_bias)
    with open(args.path, "w", encoding="utf-8") as f:
        json.dump(snap, f, separators=(",", ":"))


if __name__ == "__main__":  # pragma: no cover
    main()
