# Changelog

All notable changes to this project will be documented in this file.

## [0.0.5] - 2026-02-19

### Added
- **Python 3.5–3.14 Support**: Full compatibility across 10 Python versions.
  - Python 3.5–3.7: `rich` animations replaced with plain ANSI fallback; `importlib_metadata` backport used.
  - Python 3.8+: Full feature set with `rich` console output.
- **Security Hardening**:
  - Command injection prevention: all package names validated against PEP 508 regex and shell metacharacter blocklist before being passed to `pip`/`uv`.
  - URL sanitization: import names validated before use in PyPI API URLs to prevent path traversal.
  - Cache hardening: restrictive file permissions (600 on Unix), structure validation on load, corrupt entry rejection.
  - Symlink protection: symlinked directories and files skipped during scanning.
  - File size limit: files >10MB skipped to prevent resource exhaustion.
  - API response size limit: PyPI responses >5MB rejected.
- **Try/Except Import Detection**: New `visit_Try` AST handler correctly identifies `try: import X / except: import Y` patterns.
- **Expanded Stdlib Detection**: Fallback stdlib list expanded from 30 to 150+ modules (covers all public modules in Python 3.5–3.9).
- **30 New Common Mappings**: `attr→attrs`, `zmq→pyzmq`, `Crypto→pycryptodome`, `wx→wxPython`, `git→GitPython`, `docx→python-docx`, `kafka→kafka-python`, `nacl→PyNaCl`, `skimage→scikit-image`, and more.
- **Expanded Suspicious Packages**: 20 additional generic project names (`middleware`, `migrations`, `plugins`, `views`, `forms`, etc.) to reduce false positives.
- **Expanded Directory Exclusions**: Scanner now skips `node_modules`, `dist`, `build`, `.tox`, `.nox`, `.eggs`, `*.egg-info`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache`, `.terraform`, `.serverless`.
- **Encoding Resilience**: Parser falls back from UTF-8 to latin-1 for non-standard encoded files.

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
