# Architecture

`pypm` follows a modular pipeline approach to dependency management.

## Pipeline Steps

1.  **Scanning**: The `scanner` module traverses the directory tree, respecting `.gitignore` and skipping virtual environments (`venv`, `.env`, etc.) to find Python source files.
2.  **Parsing**: The `parser` module reads each file and uses `ast.parse()` to generate an Abstract Syntax Tree. It visits `Import` and `ImportFrom` nodes to collect module names.
3.  **Resolution**: The `resolver` is the brain of the operation.
    -   It filters out Python standard library modules (using `sys.stdlib_module_names`).
    -   It detects local modules to avoid installing your own files from PyPI.
    -   It uses a mapped lookup for common specific cases (e.g., `cv2` -> `opencv-python`).
    -   For unknown modules, it queries PyPI ensuring the package exists.
4.  **Generation**: The CLI takes the resolved list and updates `pyproject.toml` using a merging strategy that preserves existing configuration.

## Design Decisions

-   **AST over Regex**: We use AST to avoid false positives in comments or strings.
-   **Zero-Dependency Core**: The core logic relies mainly on the standard library, with `requests` for PyPI checks and `uv` for fast installation.
-   **Determinism**: Dependencies are always sorted to ensure reproducible builds.
