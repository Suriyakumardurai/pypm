import sys
from typing import List
from .utils import log, run_command, check_command_exists

def install_packages(packages: List[str]):
    """
    Installs packages using uv if available, otherwise pip.
    """
    if not packages:
        log("No packages to install.", level="INFO")
        return

    use_uv = check_command_exists("uv")
    
    if use_uv:
        log("Found uv, using it for installation...", level="INFO")
        command_str = "uv pip install "
        # Check if running in venv
        if sys.prefix == sys.base_prefix:
            log("No virtual environment detected, using --system for uv.", level="WARNING")
            command_str += "--system "
        command_str += " ".join(packages)
    else:
        log("uv not found, falling back to pip...", level="INFO")
        command_str = f"{sys.executable} -m pip install " + " ".join(packages)

    log(f"Installing: {', '.join(packages)}", level="DEBUG")
    if run_command(command_str):
        log("Successfully installed packages.", level="DEBUG")
        return True
    else:
        log("Failed to install packages.", level="ERROR")
        return False
