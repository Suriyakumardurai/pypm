import sys
import subprocess
import shlex
import logging
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("pypm")

# ANSI Colors
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Icons
Green_Check = f"{GREEN}✔{RESET}"
Red_Cross = f"{RED}✖{RESET}"
Yellow_Warn = f"{YELLOW}⚠{RESET}"

def log(message: str, level: str = "INFO"):
    """
    Wrapper around logging for compatibility with existing code.
    """
    if level == "DEBUG":
        logger.debug(f"{CYAN}[DEBUG] {message}{RESET}")
    elif level == "WARNING":
        logger.warning(f"{Yellow_Warn} {YELLOW}{message}{RESET}")
    elif level == "ERROR":
        logger.error(f"{Red_Cross} {RED}{message}{RESET}")
    else:
        logger.info(message)

def print_step(message: str):
    logger.info(f"{BOLD}{CYAN}==>{RESET} {BOLD}{message}{RESET}")

def print_success(message: str):
    logger.info(f"{Green_Check} {GREEN}{message}{RESET}")

def print_error(message: str):
    logger.error(f"{Red_Cross} {RED}{message}{RESET}")

def print_warning(message: str):
    logger.warning(f"{Yellow_Warn} {YELLOW}{message}{RESET}")

def run_command(command: str, cwd: Optional[str] = None) -> bool:
    """
    Runs a shell command. Returns True if successful, False otherwise.
    """
    try:
        # On Windows, shlex.split might not handle backslashes as expected for paths if not careful,
        # but for simple commands like 'uv pip install ...' it should be fine.
        # Check platform to decide whether to use shell=True or not (often needed on Windows for built-ins, but uv is an executable).
        # We will use shell=False and split command for better security/control, unless complex shell features are needed.
        
        args = shlex.split(command, posix=(sys.platform != "win32"))
        
        log(f"Running: {command}", level="DEBUG")
        result = subprocess.run(args, cwd=cwd, check=False, text=True, capture_output=False)
        
        if result.returncode != 0:
            log(f"Command failed with return code {result.returncode}", level="ERROR")
            return False
            
        return True
    except FileNotFoundError:
        log(f"Command not found: {command}", level="ERROR")
        return False
    except Exception as e:
        log(f"Error running command: {e}", level="ERROR")
        return False

def check_command_exists(command: str) -> bool:
    """
    Checks if a command exists effectively by trying to find it.
    """
    from shutil import which
    return which(command) is not None
