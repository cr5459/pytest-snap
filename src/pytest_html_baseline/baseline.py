from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Dict, Any, Optional
from pathlib import Path
import re

from .fingerprint import fingerprint


SNAPSHOT_VERSION = 1


def failure_signature(longrepr) -> Optional[str]:
    if not longrepr:
        return None
    try:
        first = str(longrepr).splitlines()[0]
    except Exception:
        return None
    return fingerprint(first)

# --- ID Normalization -----------------------------------------------------
_VERSION_DIR_RE = re.compile(r"(/|^)v[0-9]+(/)tests/")

def normalize_test_id(raw_id: str, mode: str | None = None) -> str:
    if not mode or mode in {"off", "none"}:
        return raw_id
    if mode == "strip_version_dir":
        return _VERSION_DIR_RE.sub(lambda m: m.group(1) + "__/tests/", raw_id)
    return raw_id


@dataclass
class TestRecord:
    id: str
    outcome: str
    duration: float
    sig: str | None

    def to_json(self) -> Dict[str, Any]:
        d = {"id": self.id, "outcome": self.outcome, "duration": round(float(self.duration), 6)}
        if self.sig:
            d["sig"] = self.sig
        return d


@dataclass
class Snapshot:
    version: int
    created_at: str
    collected: int
    tests: List[TestRecord]

    def to_json(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "collected": self.collected,
            "tests": [t.to_json() for t in self.tests],
        }


def write_snapshot(path: str, records: Iterable[TestRecord], collected: int) -> None:
    snap = Snapshot(
        version=SNAPSHOT_VERSION,
        created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        collected=collected,
        tests=list(records),
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap.to_json(), f, separators=(",", ":"), sort_keys=False)


def read_snapshot(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


# --- Rolling history ---

HISTORY_MAX = 20


def append_history(history_path: str, run_id: str, records: List[TestRecord], max_lines: int | None = None) -> None:
    entry = {
        "run_id": run_id,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tests": [
            {"id": r.id, "outcome": r.outcome, "duration": round(float(r.duration), 6)} for r in records
        ],
    }
    p = Path(history_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    # Truncate to last HISTORY_MAX (or override) lines
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
        limit = HISTORY_MAX if max_lines is None else max_lines
        if len(lines) > limit:
            p.write_text("\n".join(lines[-limit:]) + "\n", encoding="utf-8")
    except Exception:
        pass


def load_history(history_path: str) -> List[dict]:
    p = Path(history_path)
    if not p.exists():
        return []
    out = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            out.append(json.loads(line))
    except Exception:
        return []
    return out


def compute_flake_scores(history: List[dict]) -> Dict[str, float]:
    # Exponential weighted measure of outcome flips (pass<->fail) across sequential runs
    # Use alpha = 0.3
    alpha = 0.3
    last_outcome: Dict[str, str] = {}
    score: Dict[str, float] = {}
    for run in history:
        tests = run.get("tests", [])
        # build quick map
        curr = {t["id"]: t.get("outcome") for t in tests}
        for tid, out in curr.items():
            prev = last_outcome.get(tid)
            flipped = prev is not None and prev != out and {prev, out} <= {"passed", "failed"}
            prev_score = score.get(tid, 0.0)
            new_score = (1 - alpha) * prev_score + (alpha if flipped else 0.0)
            score[tid] = new_score
            last_outcome[tid] = out
    return score
