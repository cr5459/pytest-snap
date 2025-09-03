from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from typing import Optional

_VOLATILE_PAT = re.compile(r"(/[^\s:]+)+|\b0x[0-9a-fA-F]+\b|\b\d+\b|[A-F0-9]{8,}\b")
_WS = re.compile(r"\s+")


def normalize_failure_line(line: str) -> str:
    line = line.strip()
    # remove volatile tokens: paths, numbers, hex, addresses
    line = _VOLATILE_PAT.sub(" ", line)
    line = _WS.sub(" ", line)
    return line.strip().lower()


def fingerprint(first_line: Optional[str]) -> Optional[str]:
    if not first_line:
        return None
    norm = normalize_failure_line(first_line)[:500]
    if not norm:
        return None
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]


def similar(a: str, b: str, threshold: float = 0.75) -> bool:
    if a == b:
        return True
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold
