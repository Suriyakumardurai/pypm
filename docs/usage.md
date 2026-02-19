# Usage Guide

## Installation

Install globally from PyPI:

```bash
pip install pypm-cli
```

Or install from source:

```bash
git clone https://github.com/Suriyakumardurai/pypm.git
cd pypm
pip install .
```

## Python Version Compatibility

pypm 0.0.5 supports Python 3.5 through 3.14.

| Python Version | Notes |
|---|---|
| 3.5 – 3.7 | Compatible — plain ANSI output (no `rich` animations) |
| 3.8+ | Full feature set with `rich` console output |

> If `uv` is available on your system, pypm will use it for faster installs. Otherwise, it falls back to `pip`.

## Commands

### `pypm infer`

Scans the current directory (recursively) for `.py` and `.ipynb` files, extracts imports, resolves them to PyPI packages, and updates `pyproject.toml`.

```bash
pypm infer
# OR specify a path
pypm infer /path/to/project
```

**Options:**
-   `--dry-run`: Preview changes without modifying files.
-   `--verbose` / `-v`: Show detailed debug output.

### `pypm install`

Infers dependencies and then installs them into the current environment.

```bash
pypm install
```

### `pypm --version`

Displays the installed version of `pypm-cli`.

```bash
pypm --version
# Output: pypm-cli 0.0.5
```

## What Gets Detected

pypm detects dependencies from:

- **Standard imports**: `import requests`, `from flask import Flask`
- **Dynamic imports**: `importlib.import_module("redis")`, `__import__("celery")`
- **Database connection strings**: `"postgresql+asyncpg://..."` → adds `asyncpg`
- **Try/except patterns**: `try: import ujson except: import json` → adds `ujson`, skips `json`
- **Jupyter notebooks**: `.ipynb` files are parsed for code cell imports

## What Gets Skipped

- Standard library modules (150+ modules detected)
- Relative imports (`from .models import User`)
- Local project modules (auto-detected from project structure)
- Suspicious/generic names (`app`, `config`, `utils`, `models`, etc.)
- `TYPE_CHECKING` imports (typing-only, not runtime dependencies)
- Virtual environments, `node_modules`, build artifacts, IDE folders

## Best Practices

-   Run `pypm infer --dry-run` first to see what will be added.
-   Use a virtual environment for your projects. `pypm` respects the active environment.
-   Review the generated `pyproject.toml` before committing.
