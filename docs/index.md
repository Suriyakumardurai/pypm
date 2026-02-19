# pypm – Python Package Manager

Welcome to the documentation for **pypm** v0.0.5.

## Overview

`pypm` is a command-line tool designed to simplify Python dependency management. Instead of manually maintaining `requirements.txt` or `pyproject.toml`, `pypm` analyzes your source code imports and automatically generates the necessary configuration.

**Supported Python versions**: 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14

## Table of Contents

-   [Usage Guide](usage.md): How to use `pypm` commands.
-   [API Reference](api.md): Developer documentation for the internal modules.
-   [Architecture](architecture.md): How `pypm` works under the hood.

## Key Features

-   **Zero Config**: Works out of the box — no configuration needed.
-   **AST Parsing**: Static analysis for finding imports, including try/except patterns and dynamic imports.
-   **Smart Resolution**: Distinguishes between module names and package names with 60+ built-in mappings.
-   **Security First**: Input validation, URL sanitization, cache hardening, symlink protection.
-   **Cross-Platform**: Windows, macOS, Linux.
-   **Broad Compatibility**: Python 3.5 through 3.14.

## Author

**D. Suriya Kumar**
Email: suriyakumardurai.sk.in@gmail.com
GitHub: [Suriyakumardurai/pypm](https://github.com/Suriyakumardurai/pypm)
