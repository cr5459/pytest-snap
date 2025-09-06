from __future__ import annotations

# Allow `python -m pytest_snap` to run the CLI entry point.
from .cli import main


def _main() -> int:
    return main()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
