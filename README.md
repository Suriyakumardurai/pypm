<div align="center">
  <img src="https://raw.githubusercontent.com/Suriyakumardurai/pypm/main/assets/pypm.png" alt="pypm" width="100%" />
</div>

# pypm – Python Package Manager

[![PyPI version](https://img.shields.io/pypi/v/pypm-cli.svg)](https://pypi.org/project/pypm-cli/)
[![Python versions](https://img.shields.io/pypi/pyversions/pypm-cli.svg?cacheSeconds=0)](https://pypi.org/project/pypm-cli/)
[![License](https://img.shields.io/pypi/l/pypm-cli)](https://pypi.org/project/pypm-cli/)
[![CI](https://github.com/Suriyakumardurai/pypm/actions/workflows/ci.yml/badge.svg)](https://github.com/Suriyakumardurai/pypm/actions/workflows/ci.yml)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

pypm is a zero-config CLI tool that automatically infers dependencies from your Python source code.

## ⚡ Lightning-Fast Performance
pypm is optimized for speed and efficiency:
- **Sub-200ms Inference**: Scans and parses projects in milliseconds.
- **Overlapping Pipeline**: Directory scanning and file parsing run in parallel.
- **Smart Caching**: `mtime`-based import caching skips unchanged files.
- **Memory-Aware**: Dynamic worker scaling for systems with limited RAM (e.g., 4GB).

## 🐍 Supported Python Versions

| Version | Status |
|---------|--------|
| Python 3.5 – 3.7 | ✅ Compatible (**vermin** verified) |
| Python 3.8 – 3.14 | ✅ Fully supported (CI tested) |

## 🚀 Installation

Install from PyPI:

```bash
pip install pypm-cli
```

After installation, you can run:

```bash
pypm --help
```

## ⚡ Quick Start

Scan the current directory and generate/update `pyproject.toml`:

```bash
pypm infer
```

### 2️⃣ Benchmarking speed
Measure precisely how fast pypm is on your project:

```bash
pypm infer --bench
```

### 3️⃣ Dry Run (Preview Only)
See what would be added without modifying files:

```bash
pypm infer --dry-run
```

### 4️⃣ Infer + Install Dependencies
Infer and install packages automatically:

```bash
pypm install --bench
```

> **Note:** If `uv` is available, it will be used for faster installs. Otherwise, it falls back to `pip`.

## ✨ Features

- **Blazing Fast**: Sub-200ms execution on typical projects using overlapping I/O pipelines and `mtime` caching.
- **Offline-First Mapping**: Uses a bundled database of 200+ popular packages to resolve dependencies instantly without network.
- **Smart Inference**: Recursively scans your project for `.py` and `.ipynb` files and extracts all imports.
- **Automatic Resolution**: Maps module names to actual PyPI packages (e.g., `PIL` → `Pillow`, `zmq` → `pyzmq`, `attr` → `attrs`).
- **Standard Library Detection**: Automatically ignores 150+ Python built-in and stdlib modules.
- **Try/Except Import Detection**: Handles `try: import ujson except: import json` patterns correctly.
- **Database DSN Detection**: Automatically detects database dependencies from connection strings.
- **Dynamic Import Detection**: Catches `importlib.import_module()` and `__import__()` calls.
- **Framework-Aware**: Adds extras for FastAPI, Django, Flask, Celery, SQLAlchemy, etc.
- **Modern Standards**: Generates PEP 621–compliant `pyproject.toml`.
- **Secure**: Validates all package names before shell execution, sanitizes PyPI URLs, hardens cache files.

## 🔒 Security

pypm 0.0.6 includes built-in protections:

- **Command injection prevention**: All package names are validated against PEP 508 and checked for shell metacharacters before being passed to `pip`/`uv`.
- **URL sanitization**: Import names are validated before being used in PyPI API URLs to prevent path traversal.
- **Cache hardening**: Cache files use restrictive permissions (600 on Unix) and entries are validated on load.
- **Symlink protection**: Symlinked directories and files are skipped during scanning.
- **File size limits**: Files larger than 10MB are skipped to prevent resource exhaustion.

## 📌 Example Workflow

```bash
# Inside your Python project
pypm infer

# Review generated pyproject.toml
cat pyproject.toml

# Install dependencies
pypm install
```

## 🧠 Why pypm?

Manually maintaining dependencies leads to:
- Duplicate effort
- Forgotten imports
- Mismatched environments
- Dirty `requirements.txt` files

**pypm makes your imports the single source of truth.**

## 📚 Documentation

See full documentation in: `docs/`

## 🔧 Development Setup

If you want to contribute or run locally:

```bash
git clone https://github.com/Suriyakumardurai/pypm.git
cd pypm
pip install -e .[dev]
```

## 📦 Project

Available on PyPI: https://pypi.org/project/pypm-cli/
