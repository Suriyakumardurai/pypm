import os
from pathlib import Path
from typing import Iterator, List  # noqa: F401

from .utils import log

# Directories to always skip during scanning
IGNORED_DIR_NAMES = frozenset({
    # Virtual environments
    ".venv", "venv", "env", ".env",
    # Version control
    ".git", ".hg", ".svn",
    # IDE / Editor
    ".idea", ".vscode", ".vs",
    # Python caches
    "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    # Build artifacts
    "dist", "build", ".eggs", "*.egg-info",
    # Testing tools
    ".tox", ".nox",
    # Node.js (common in mixed projects)
    "node_modules",
    # Other
    ".terraform", ".serverless",
})


def is_virtual_env(path):
    # type: (Path) -> bool
    """
    Heuristic to check if a directory should be skipped.
    Checks for virtual environments, caches, build dirs, IDE dirs, etc.
    """
    name = path.name

    # Fast check: is the name in the ignored set?
    if name in IGNORED_DIR_NAMES:
        return True

    # Glob-style: *.egg-info directories
    if name.endswith(".egg-info"):
        return True

    # Virtual environment indicators (for custom-named venvs)
    if (path / "pyvenv.cfg").exists():
        return True
    if (path / "bin" / "activate").exists():
        return True
    if (path / "Scripts" / "activate").exists():
        return True

    return False


def iter_scan_directory(root_path):
    # type: (Path) -> Iterator[Path]
    """
    Generator that yields .py/.ipynb files as they're discovered.
    Enables pipeline: files can be parsed while scanning continues.
    Uses os.scandir() for fast directory iteration.
    """
    stack = [root_path]

    while stack:
        current_dir = stack.pop()
        try:
            with os.scandir(str(current_dir)) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue

                        if entry.is_dir(follow_symlinks=False):
                            dir_path = Path(entry.path)
                            if not is_virtual_env(dir_path):
                                stack.append(dir_path)
                        elif entry.is_file(follow_symlinks=False):
                            name = entry.name
                            if name.endswith(".py") or name.endswith(".ipynb"):
                                yield Path(entry.path)
                    except OSError:
                        continue
        except PermissionError as e:
            log("Permission denied accessing %s: %s" % (str(current_dir), str(e)), level="ERROR")
        except OSError:
            continue


def scan_directory(root_path):
    # type: (Path) -> List[Path]
    """
    Recursively scans the directory for .py files.
    Wraps iter_scan_directory for backward compatibility.
    """
    return list(iter_scan_directory(root_path))

