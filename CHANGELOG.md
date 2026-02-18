# Changelog

All notable changes to this project will be documented in this file.

## [0.0.4] - 2026-02-18

### Fixed
- Resolved all static type checking errors found by `mypy` in CI.
- Optimized imports and improved PEP8 compliance across core modules.

## [0.0.3] - 2026-02-18

### Added
- **Hyper-Fast Resolution**: Dramatically improved `pypm infer` speed (scans 1000+ files in < 1s).
- **Bundled Metadata DB**: Added a local database of popular PyPI packages to bypass network lookups.
- **Persistent Caching**: Implemented a local metadata cache at `~/.cache/pypm/cache.json`.
- **Parallel Scanning**: AST parsing and dependency resolution are now fully parallelized.

### Fixed
- Fixed case-sensitivity issues in imports (e.g., `PIL` vs `pil`).
- Improved namespace package resolution (e.g., `google.cloud.storage`).
- Prevented submodule "pollution" in inferred dependencies (e.g., `fastapi.Depends` -> `fastapi`).
- Standardized underscore/hyphen handling for packages like `python-dotenv`.

## [0.0.2] - 2026-02-17

### Fixed
- Fixed crash on Python 3.9 due to `sys.stdlib_module_names` missing attribute.
- Resolved `mypy` static analysis errors for Python 3.9 CI jobs.
- Updated dependency resolution to be more robust across Python versions.

## [0.0.1] - 2026-02-16

### Added
- Initial release
- AST-based import parsing
- PyPI resolution logic
- CLI with `infer` and `install` commands
- GitHub Actions CI workflow
