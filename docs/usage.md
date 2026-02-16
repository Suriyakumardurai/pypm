# Usage Guide

## Installation

```bash
git clone https://github.com/Suriyakumardurai/pypm.git
cd pypm
pip install .
```

This will also install `uv` for fast package management.

## Commands

### `pypm infer`

Scans the current directory (recursively) for `.py` files, extracts imports, resolves them to PyPI packages, and updates `pyproject.toml`.

```bash
pypm infer
# OR
pypm infer /path/to/project
```

**Options:**
-   `--dry-run`: Preview changes without modifying files.

### `pypm install`

Infers dependencies and then installs them into the current environment.

```bash
pypm install
```

### `pypm --version`

Displays the installed version of `pypm-cli`.

## Best Practices

-   Run `pypm infer --dry-run` first to see what will be added.
-   Use a virtual environment for your projects. `pypm` respects the active environment.
