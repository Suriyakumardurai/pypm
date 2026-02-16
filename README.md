# pypm - Python Project Manager

**pypm** is a smart, zero-config CLI tool that automatically infers dependencies from your Python source code.

> **Stop writing dependencies twice.** Let your imports define your project.

`pypm` uses AST-based parsing to detect imports, resolves them to PyPI packages (handling distinct names like `PIL` -> `Pillow`), and generates a `pyproject.toml` for you.

## Features

- **Smart Inference**:Scans your project for `.py` files and extracts all imports.
- **Auto-Resolution**: Maps imports (e.g., `import cv2`) to their actual PyPI packages (e.g., `opencv-python`).
- **Standard Library Detection**: Automatically ignores Python standard library modules.
- **Zero Config**: No need to manually list dependencies in `requirements.txt` or `pyproject.toml`.
- **Modern Standards**: Generates PEP 621 compliant `pyproject.toml` files.

## Installation

(Coming soon - for now, clone and run locally)

```bash
git clone https://github.com/Suriyakumardurai/pypm.git
cd pypm
pip install .
```

## Quick Start

1.  **Infer Dependencies**: Scan your current directory and update `pyproject.toml`.
    ```bash
    pypm infer
    ```

2.  **Install Dependencies**: Install the inferred packages (uses `uv` if available, else `pip`).
    ```bash
    pypm install
    ```

## Documentation

For full documentation, see [docs/index.md](docs/index.md).
