# Changelog

All notable changes to this project will be documented in this file.

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
