import os
from pathlib import Path
from typing import List  # noqa: F401
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


def scan_directory(root_path):
    # type: (Path) -> List[Path]
    """
    Recursively scans the directory for .py files, excluding git, venvs, etc.
    Symlinks are not followed to prevent infinite loops and path traversal.
    """
    py_files = []  # type: List[Path]

    try:
        # Walk the tree (followlinks=False is the default, but explicit is better)
        for root, dirs, files in os.walk(root_path, followlinks=False):
            current_root = Path(root)

            # Modify dirs in-place to skip ignored directories
            # Also skip symlinked directories for security
            filtered_dirs = []
            for d in dirs:
                dir_path = current_root / d
                # Skip symlinks to prevent infinite loops and path traversal
                if dir_path.is_symlink():
                    log("Skipping symlinked directory: %s" % str(dir_path), level="DEBUG")
                    continue
                if is_virtual_env(dir_path):
                    continue
                filtered_dirs.append(d)
            dirs[:] = filtered_dirs

            for file in files:
                if file.endswith(".py") or file.endswith(".ipynb"):
                    file_path = current_root / file
                    # Skip symlinked files too
                    if file_path.is_symlink():
                        log("Skipping symlinked file: %s" % str(file_path), level="DEBUG")
                        continue
                    py_files.append(file_path)

    except PermissionError as e:
        log("Permission denied accessing %s: %s" % (str(root_path), str(e)), level="ERROR")

    return py_files
