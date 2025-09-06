from __future__ import annotations

"""Performance budgets helpers (migrated)."""

import json
from typing import Dict, List

try:  # pragma: no cover
    import importlib
    yaml = importlib.import_module("yaml")  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


def load_budgets(path: str | None) -> Dict[str, Dict[str, float]]:
    if not path:
        return {}
    try:
        if path.endswith(('.yml', '.yaml')) and yaml:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        else:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        return data.get('budgets', {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def p95(durations: List[float]) -> float:
    if not durations:
        return 0.0
    if len(durations) < 5:
        return max(durations)
    sorted_ds = sorted(durations)
    idx = int(round(0.95 * (len(sorted_ds) - 1)))
    return float(sorted_ds[idx])


def compute_budget_violations(budgets: Dict[str, Dict[str, float]], observed: Dict[str, List[float]]) -> List[dict]:
    violations = []
    for tid, spec in budgets.items():
        want_p95 = float(spec.get('p95', 0.0))
        if tid not in observed:
            continue
        obs_p95 = p95(observed[tid])
        if obs_p95 > 0 and want_p95 > 0:
            if obs_p95 >= want_p95 * 1.15 and (obs_p95 - want_p95) >= 0.05:
                violations.append({
                    'id': tid,
                    'budget_p95': round(want_p95, 6),
                    'observed_p95': round(obs_p95, 6),
                })
    return violations

__all__ = [
    'load_budgets',
    'compute_budget_violations',
    'p95',
]
