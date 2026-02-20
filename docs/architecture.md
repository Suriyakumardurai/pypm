# Architecture

`pypm` v0.0.6 follows a modular pipeline approach to dependency management.

## Pipeline Steps

1.  **Scanning** (`scanner.py`): Traverses the directory tree using an ultra-fast generator. Finds all `.py` and `.ipynb` files.

2.  **Parsing** (`parser.py`): Reads each file and uses `ast.parse()`.
    - **Caching**: Uses `mtime` + size-based caching to skip re-parsing unchanged files.
    - **Pre-filtering**: Checks for `"import"` keywords before parsing to skip no-import files.
    - **Visitor**: The `ImportVisitor` class visits:
    - `Import` and `ImportFrom` nodes for standard imports
    - `If` nodes to detect `TYPE_CHECKING` blocks (typing-only imports are separated)
    - `Try` nodes to handle `try/except ImportError` patterns (optional dependencies)
    - `Call` nodes to detect `importlib.import_module()` and `__import__()` dynamic imports
    - `Constant` / `Str` nodes to detect database connection strings in string literals

3.  **Resolution** (`resolver.py`): The brain of the operation.
    -   Filters standard library modules (O(1) batch filtering).
    -   Detects and filters local project modules.
    -   Uses `COMMON_MAPPINGS` (75+ entries) for fast lookup.
    -   Checks `KNOWN_PYPI_PACKAGES` bundled database (200+ packages).
    -   Queries PyPI in parallel (up to 128 workers) using connection pooling.
    -   Applies framework-specific extras.

4.  **Generation** (`cli.py`): Takes the resolved list and updates `pyproject.toml` using a merging strategy that preserves existing configuration.

## Security Architecture

-   **Input validation**: Package names are validated at two boundaries — before PyPI URL construction (`pypi.py`) and before shell command execution (`installer.py`).
-   **Cache integrity**: Disk cache is validated on load, uses restrictive file permissions (600 on Unix), and rejects corrupt entries.
-   **Symlink protection**: Scanner skips all symlinked paths to prevent infinite loops and directory traversal.
-   **Resource limits**: Max file size (10MB) and max API response size (5MB) prevent resource exhaustion.

## Design Decisions

-   **AST over Regex**: We use AST to avoid false positives in comments or strings.
-   **Try/Except Awareness**: The parser understands import fallback patterns, so `try: import ujson except: import json` correctly adds `ujson` without falsely adding `json`.
-   **Zero-Dependency Core**: The core logic relies mainly on the standard library, with `rich` (optional, Python 3.8+) for console output and `uv` (optional) for fast installation.
-   **Determinism**: Dependencies are always sorted to ensure reproducible builds.
-   **Broad Compatibility**: All source code uses `%` string formatting (no f-strings) and `typing` module generics for Python 3.5+ support.
