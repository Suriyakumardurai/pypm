import sys
import subprocess
import shlex
from typing import Optional
from rich.console import Console
from rich.theme import Theme

# Custom Theme
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "step": "bold cyan",
    "cmd": "dim",
})

# Initialize Console
console = Console(theme=custom_theme)

# Legacy ANSI Colors (Kept for compatibility if imported elsewhere, but should be phased out)
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Global Verbosity Flag
VERBOSE = False

def log(message: str, level: str = "INFO"):
    """
    Wrapper around console.log/print.
    """
    if level == "DEBUG":
        if VERBOSE:
            console.print(f"[dim][DEBUG] {message}[/dim]")
    elif level == "WARNING":
        console.print(f"[warning]⚠ {message}[/warning]")
    elif level == "ERROR":
        console.print(f"[error]✖ {message}[/error]")
    else:
        console.print(message)

def print_step(message: str):
    console.print(f"[step]==>[/step] [bold]{message}[/bold]")

def print_success(message: str):
    console.print(f"[success]✔ {message}[/success]")

def print_error(message: str):
    console.print(f"[error]✖ {message}[/error]")

def print_warning(message: str):
    console.print(f"[warning]⚠ {message}[/warning]")

def run_command(command: str, cwd: Optional[str] = None) -> bool:
    """
    Runs a shell command. Returns True if successful, False otherwise.
    """
    try:
        args = shlex.split(command, posix=(sys.platform != "win32"))
        
        # log(f"Running: {command}", level="DEBUG") # Too verbose for normal run
        result = subprocess.run(args, cwd=cwd, check=False, text=True, capture_output=False)
        
        if result.returncode != 0:
            console.print(f"[error]Command failed with return code {result.returncode}[/error]")
            return False
            
        return True
    except FileNotFoundError:
        console.print(f"[error]Command not found: {command}[/error]")
        return False
    except Exception as e:
        console.print(f"[error]Error running command: {e}[/error]")
        return False

def check_command_exists(command: str) -> bool:
    """
    Checks if a command exists effectively by trying to find it.
    """
    from shutil import which
    return which(command) is not None
