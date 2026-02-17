# pypm – Python Project Manager

[![PyPI version](https://img.shields.io/pypi/v/pypm-cli.svg)](https://pypi.org/project/pypm-cli/)
[![Python](https://img.shields.io/pypi/pyversions/pypm-cli)](https://pypi.org/project/pypm-cli/)
[![License](https://img.shields.io/pypi/l/pypm-cli)](https://pypi.org/project/pypm-cli/)
[![CI](https://github.com/Suriyakumardurai/pypm/actions/workflows/ci.yml/badge.svg)](https://github.com/Suriyakumardurai/pypm/actions/workflows/ci.yml)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

pypm is a zero-config CLI tool that automatically infers dependencies from your Python source code.

> **Stop writing dependencies twice. Let your imports define your project.**

pypm parses your project using Python’s AST, detects imports, resolves them to their correct PyPI package names (e.g., `PIL` → `Pillow`, `cv2` → `opencv-python`), and generates a modern `pyproject.toml` for you.

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

### 1️⃣ Infer Dependencies

Scan the current directory and generate/update `pyproject.toml`:

```bash
pypm infer
```

### 2️⃣ Infer + Install Dependencies

Infer and install packages automatically:

```bash
pypm install
```

> **Note:** If `uv` is available, it will be used for faster installs. Otherwise, it falls back to `pip`.

## ✨ Features

- **Smart Inference**: Recursively scans your project for `.py` files and extracts all imports.
- **Automatic Resolution**: Maps module names to actual PyPI packages:
  - `PIL` → `Pillow`
  - `cv2` → `opencv-python`
  - and many more
- **Standard Library Detection**: Automatically ignores Python built-in and stdlib modules.
- **Zero Configuration**: No manual `requirements.txt` maintenance.
- **Modern Standards**: Generates PEP 621–compliant `pyproject.toml`.

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
pip install -e .
```

## 📦 Project

Available on PyPI: https://pypi.org/project/pypm-cli/
