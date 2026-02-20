# API Reference

This section documents the internal modules of `pypm` v0.0.6.

## `pypm.scanner`

Handles file system traversal, virtual environment detection, and directory exclusions.

-   `scan_directory(root_path: Path) -> List[Path]`: Recursively finds `.py` and `.ipynb` files. Skips virtual environments, `node_modules`, build artifacts, IDE folders, and symlinks.
-   `is_virtual_env(path: Path) -> bool`: Checks if a directory should be skipped (venvs, caches, build dirs, etc.).
-   `IGNORED_DIR_NAMES`: Frozenset of directory names that are always skipped.

## `pypm.parser`

Uses Python's AST to extract imports with edge case handling.

-   `get_imports_from_file(filepath: Path) -> dict`: Returns a dict with keys `runtime`, `typing`, and `dynamic` — each a `Set[str]` of module names.
-   `get_imports_from_notebook(filepath: Path) -> dict`: Parses Jupyter notebooks for imports.
-   `ImportVisitor`: AST node visitor that handles:
    -   Standard `import` and `from ... import` statements
    -   `if TYPE_CHECKING:` blocks (separates typing-only imports)
    -   `try/except ImportError` blocks (detects optional dependencies)
    -   `importlib.import_module()` and `__import__()` calls (dynamic imports)
    -   Database connection string detection in string literals
-   `MAX_FILE_SIZE_BYTES`: Files larger than this (10MB) are skipped.

## `pypm.resolver`

The core logic for mapping imports to PyPI packages.

-   `resolve_dependencies(imports: Set[str], project_root: str, known_local_modules: Set[str]) -> List[str]`:
    1.  Filters standard library modules (150+ on Python < 3.10, `sys.stdlib_module_names` on 3.10+).
    2.  Filters local project modules.
    3.  Filters suspicious/generic names (40+ common project names).
    4.  Resolves via `COMMON_MAPPINGS` (60+ entries, e.g., `PIL` → `Pillow`).
    5.  Checks bundled `KNOWN_PYPI_PACKAGES` database (200+ packages).
    6.  Falls back to online PyPI verification (parallelized, 50 workers).
    7.  Applies framework extras (FastAPI, Django, Flask, etc.).
    8.  Deduplicates and merges extras.
-   `is_stdlib(module_name: str) -> bool`: Checks if a module is in the standard library.
-   `COMMON_MAPPINGS`: Dict of 60+ import name → PyPI package name mappings.
-   `FRAMEWORK_EXTRAS`: Dict of framework → recommended additional packages.
-   `SUSPICIOUS_PACKAGES`: Set of 40+ generic names that are likely local modules.

## `pypm.pypi`

Utilities for interacting with the Python Package Index, with security hardening.

-   `check_package_exists(name: str) -> bool`: Checks if a project exists on PyPI (cached).
-   `get_pypi_metadata(name: str) -> Optional[dict]`: Fetches full PyPI metadata with validation.
-   `get_latest_version(name: str) -> Optional[str]`: Fetches the latest version string.
-   `find_pypi_package(import_name: str) -> Optional[str]`: Tries exact match then common name variations.
-   `get_package_extras(name: str) -> List[str]`: Fetches available extras for a package.
-   Security features: URL sanitization, cache validation, response size limits, file permissions.

## `pypm.installer`

Package installation with security validation.

-   `install_packages(packages: List[str]) -> bool`: Installs packages via `uv` (preferred) or `pip`. All names validated before shell execution.
-   `_is_safe_package_name(name: str) -> bool`: Validates package names against PEP 508 and shell metacharacter blocklist.

## `pypm.db`

Bundled database of popular PyPI packages.

-   `KNOWN_PYPI_PACKAGES`: Set of 200+ common package names used for fast offline resolution.

## `pypm.cli`

Entry point for the command-line interface. Commands: `infer`, `install`, `--version`.
