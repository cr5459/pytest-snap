from __future__ import annotations

"""Configuration object for runtime thresholds and gating (migrated)."""

from dataclasses import dataclass
import os
from typing import Literal

FailOn = Literal["new-failures", "slower", "budgets", "any"]


@dataclass(frozen=True)
class BaselineConfig:
    slower_ratio: float = 1.30
    slower_abs: float = 0.20
    min_count: int = 0
    fail_on: FailOn = "new-failures"
    flake_threshold: float = 0.15
    history_path: str | None = None
    history_max: int = 20

    @classmethod
    def from_options(cls, config) -> "BaselineConfig":  # type: ignore[override]
        opt = config.option
        slower_ratio = float(_env_or("HTML_SLOWER_RATIO", getattr(opt, "html_slower_threshold_ratio", 1.30)))
        slower_abs = float(_env_or("HTML_SLOWER_ABS", getattr(opt, "html_slower_threshold_abs", 0.20)))
        min_count = int(_env_or("HTML_MIN_COUNT", getattr(opt, "html_min_count", 0)))
        fail_on = str(_env_or("HTML_FAIL_ON", getattr(opt, "html_fail_on", "new-failures")))  # type: ignore[assignment]
        if fail_on not in {"new-failures", "slower", "budgets", "any"}:
            fail_on = "new-failures"
        flake_threshold = float(_env_or("HTML_FLAKE_THRESHOLD", getattr(opt, "html_flake_threshold", 0.15)))
        raw_hist_path = _env_or("HTML_HISTORY_PATH", getattr(opt, "html_history_path", ".artifacts/history.jsonl"))
        if raw_hist_path is None or str(raw_hist_path).strip() == "":
            raw_hist_path = ".artifacts/history.jsonl"
        if str(raw_hist_path).lower() in {"off", "none", "false", "0"}:
            history_path = None
        else:
            history_path = str(raw_hist_path)
        raw_hist_max = _env_or("HTML_HISTORY_MAX", getattr(opt, "html_history_max", None))
        history_max = 20
        try:
            if raw_hist_max not in (None, ""):
                history_max = int(raw_hist_max)  # type: ignore[arg-type]
        except Exception:
            history_max = 20
        return cls(
            slower_ratio=slower_ratio,
            slower_abs=slower_abs,
            min_count=min_count,
            fail_on=fail_on,  # type: ignore[arg-type]
            flake_threshold=flake_threshold,
            history_path=history_path,
            history_max=history_max,
        )  # type: ignore[arg-type]


def _env_or(name: str, default):
    v = os.getenv(name)
    return v if v is not None else default

__all__ = ["BaselineConfig", "FailOn"]
