# API Reference

This section documents the internal modules of `pypm`.

## `pypm.scanner`

Handles file system traversal and virtual environment detection.

-   `scan_directory(root_path: Path) -> List[Path]`: Recursively finds `.py` files.
-   `is_virtual_env(path: Path) -> bool`: Checks if a directory is likely a virtualenv.

## `pypm.parser`

Uses Python's AST to extract imports.

-   `get_imports_from_file(filepath: Path) -> Set[str]`: returns a set of module names imported in a file.

## `pypm.resolver`

The core logic for mapping imports to PyPI packages.

-   `resolve_dependencies(imports: Set[str], project_root: str) -> List[str]`:
    1.  Filters standard library modules.
    2.  Filters local modules.
    3.  Checks online PyPI availability.
    4.  Resolves package names (e.g., `PIL` -> `Pillow`).

## `pypm.pypi`

Utilities for interacting with the Python Package Index.

-   `check_package_exists(name: str) -> bool`: Checks if a project exists on PyPI.
-   `get_latest_version(name: str) -> str`: Fetches the latest version string.

## `pypm.cli`

Entry point for the command-line interface.
