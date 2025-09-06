# Changelog

This project has not been formally released yet. History is reset while the
public API & feature surface is still being stabilized pre-1.0.0.

## [0.1.1] - Unreleased
### Fixed
- `--example-suite` flag now properly runs versioned example suite directories for `run` / `all` instead of defaulting to root `tests/`.

## [0.1.0] - 2025-09-04
### Added
- Minimal pytest plugin exposing the `--snap` flag to capture per-test outcome
	+ duration (ns) into a JSON file (`--snap-out`).
- Placeholder options for future baseline / gating (`--snap-baseline`,
	`--snap-fail-on`) – currently inert.
- Type marker file `py.typed`.
- Modern PEP 621 `pyproject.toml` with pytest11 entry point.

### Notes
- Pre-1.0.0 the JSON snapshot schema and flags may evolve without deprecation.
- Earlier experimental namespaces and legacy compatibility packages were
	removed prior to first release and are intentionally not listed here.
