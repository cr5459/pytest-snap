from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Literal

FailOn = Literal["new-failures", "slower", "any"]


@dataclass(frozen=True)
class BaselineConfig:
    slower_ratio: float = 1.30
    slower_abs: float = 0.20
    min_count: int = 0
    fail_on: FailOn = "new-failures"

    @classmethod
    def from_options(cls, config) -> "BaselineConfig":  # type: ignore[override]
        # pytest Config object contains the option values
        opt = config.option
        slower_ratio = float(_env_or("HTML_SLOWER_RATIO", getattr(opt, "html_slower_threshold_ratio", 1.30)))
        slower_abs = float(_env_or("HTML_SLOWER_ABS", getattr(opt, "html_slower_threshold_abs", 0.20)))
        min_count = int(_env_or("HTML_MIN_COUNT", getattr(opt, "html_min_count", 0)))
        fail_on = str(_env_or("HTML_FAIL_ON", getattr(opt, "html_fail_on", "new-failures")))  # type: ignore[assignment]
        if fail_on not in {"new-failures", "slower", "any"}:
            fail_on = "new-failures"
        return cls(slower_ratio=slower_ratio, slower_abs=slower_abs, min_count=min_count, fail_on=fail_on)  # type: ignore[arg-type]


def _env_or(name: str, default):
    v = os.getenv(name)
    return v if v is not None else default
