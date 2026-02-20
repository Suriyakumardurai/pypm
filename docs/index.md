# pypm – Python Package Manager

Welcome to the documentation for **pypm** v0.0.6.

## Overview

`pypm` v0.0.6 follows a modular pipeline approach to dependency management. Instead of manually maintaining `requirements.txt` or `pyproject.toml`, `pypm` analyzes your source code imports and automatically generates the necessary configuration.

**Supported Python versions**: 3.5 – 3.14 (Verified)

## Table of Contents

-   [Usage Guide](usage.md): How to use `pypm` commands.
-   [API Reference](api.md): This section documents the internal modules of `pypm` v0.0.6.
-   [Architecture](architecture.md): How `pypm` works under the hood.

## Key Features

**Options:**
-   `--dry-run`: Preview changes without modifying files.
-   `--bench`: Display high-precision execution timing for analysis and total run.
-   `--verbose` / `-v`: Show detailed debug output.
- 1.  **Scanning** (`scanner.py`): Traverses the directory tree using an ultra-fast generator. Finds all `.py` and `.ipynb` files.

2.  **Parsing** (`parser.py`): Reads each file and uses `ast.parse()`.
    - **Caching**: Uses `mtime` + size-based caching to skip re-parsing unchanged files.
    - **Pre-filtering**: Checks for `"import"` keywords before parsing to skip no-import files.
    - **Visitor**: The `ImportVisitor` class visits:
-   **Zero Config**: Works out of the box — no configuration needed.
-   **AST Parsing**: Static analysis for finding imports, including try/except patterns and dynamic imports.
-   **Smart Resolution**: Distinguishes between module names and package names with 60+ built-in mappings.
-   **Security First**: Input validation, URL sanitization, cache hardening, symlink protection.
-   **Cross-Platform**: Windows, macOS, Linux.
-   **Broad Compatibility**: pypm 0.0.6 supports Python 3.5 through 3.14.

| Python Version | Notes |
|---|---|
| 3.5 – 3.7 | Compatible — verified with **vermin**; plain ANSI fallback |
| 3.8 – 3.14 | Full feature set with `rich` console output |

## Author

**D. Suriya Kumar**
Email: suriyakumardurai.sk.in@gmail.com
GitHub: [Suriyakumardurai/pypm](https://github.com/Suriyakumardurai/pypm)
