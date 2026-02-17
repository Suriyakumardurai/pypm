import os
from pathlib import Path
from typing import List
from .utils import log

def is_virtual_env(path: Path) -> bool:
    """
    Simple heuristic to check if a directory is a virtual environment.
    """
    # Common venv indicators
    return (path / "pyvenv.cfg").exists() or \
           (path / "bin" / "activate").exists() or \
           (path / "Scripts" / "activate").exists() or \
           path.name in (".venv", "venv", "env", ".git", ".idea", "__pycache__", "tests", "test", "testing")

def scan_directory(root_path: Path) -> List[Path]:
    """
    Recursively scans the directory for .py files, excluding git, venvs, etc.
    """
    py_files: List[Path] = []
    
    try:
        # Walk the tree
        for root, dirs, files in os.walk(root_path):
            current_root = Path(root)
            
            # Modify dirs in-place to skip ignored directories and test directories
            dirs[:] = [d for d in dirs if not is_virtual_env(current_root / d) and d not in ("tests", "test", "testing")]
            
            for file in files:
                if file.endswith(".py"):
                    # Skip test files
                    if file.startswith("test_") or file.endswith("_test.py") or file in ("test.py", "tests.py"):
                        continue
                        
                    py_files.append(current_root / file)
                    
    except PermissionError as e:
        log(f"Permission denied accessing {root_path}: {e}", level="ERROR")
        
    return py_files
