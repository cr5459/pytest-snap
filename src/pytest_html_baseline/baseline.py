from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Dict, Any


SNAPSHOT_VERSION = 1


def failure_signature(longrepr) -> str | None:
    if not longrepr:
        return None
    try:
        first = str(longrepr).splitlines()[0].strip()
    except Exception:
        return None
    if not first:
        return None
    # Truncate long line for stability before hashing
    if len(first) > 500:
        first = first[:500]
    h = hashlib.sha1(first.encode("utf-8"))
    return h.hexdigest()[:12]


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
