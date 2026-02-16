import pytest
from pathlib import Path
from pypm.scanner import is_virtual_env

def test_is_virtual_env_true(tmp_path):
    # Case 1: pyvenv.cfg exists
    venv_dir = tmp_path / "venv"
    venv_dir.mkdir()
    (venv_dir / "pyvenv.cfg").touch()
    assert is_virtual_env(venv_dir) is True

    # Case 2: bin/activate exists
    venv_dir2 = tmp_path / "env"
    venv_dir2.mkdir()
    (venv_dir2 / "bin").mkdir()
    (venv_dir2 / "bin" / "activate").touch()
    assert is_virtual_env(venv_dir2) is True

def test_is_virtual_env_false(tmp_path):
    # Case: Normal directory
    normal_dir = tmp_path / "src"
    normal_dir.mkdir()
    assert is_virtual_env(normal_dir) is False

def test_is_virtual_env_name_match(tmp_path):
    # Case: Name is .venv
    dot_venv = tmp_path / ".venv"
    dot_venv.mkdir()
    assert is_virtual_env(dot_venv) is True
