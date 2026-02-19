import sys
import subprocess
import shlex

# --- Rich Compatibility Layer ---
# On Python < 3.8 or if rich is not installed, fall back to plain print.
try:
    from rich.console import Console
    from rich.theme import Theme

    custom_theme = Theme({
        "info": "dim cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "step": "bold cyan",
        "cmd": "dim",
    })
    console = Console(theme=custom_theme)
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    console = None  # type: ignore[assignment]

# Legacy ANSI Colors (Used as fallback when rich is not available)
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# Global Verbosity Flag
VERBOSE = False


def log(message, level="INFO"):
    """
    Wrapper around console.log/print.
    """
    if level == "DEBUG":
        if VERBOSE:
            if HAS_RICH:
                console.print("[dim][DEBUG] %s[/dim]" % message)
            else:
                sys.stderr.write("%s[DEBUG] %s%s\n" % (DIM, message, RESET))
    elif level == "WARNING":
        if HAS_RICH:
            console.print("[warning]\u26a0 %s[/warning]" % message)
        else:
            sys.stderr.write("%s\u26a0 %s%s\n" % (YELLOW, message, RESET))
    elif level == "ERROR":
        if HAS_RICH:
            console.print("[error]\u2716 %s[/error]" % message)
        else:
            sys.stderr.write("%s\u2716 %s%s\n" % (RED, message, RESET))
    else:
        if HAS_RICH:
            console.print(message)
        else:
            print(message)


def print_step(message):
    if HAS_RICH:
        console.print("[step]==> [/step] [bold]%s[/bold]" % message)
    else:
        print("%s==>%s %s%s%s" % (CYAN, RESET, BOLD, message, RESET))


def print_success(message):
    if HAS_RICH:
        console.print("[success]\u2714 %s[/success]" % message)
    else:
        print("%s\u2714 %s%s" % (GREEN, message, RESET))


def print_error(message):
    if HAS_RICH:
        console.print("[error]\u2716 %s[/error]" % message)
    else:
        sys.stderr.write("%s\u2716 %s%s\n" % (RED, message, RESET))


def print_warning(message):
    if HAS_RICH:
        console.print("[warning]\u26a0 %s[/warning]" % message)
    else:
        sys.stderr.write("%s\u26a0 %s%s\n" % (YELLOW, message, RESET))


def run_command(command, cwd=None):
    """
    Runs a shell command. Returns True if successful, False otherwise.
    """
    try:
        args = shlex.split(command, posix=(sys.platform != "win32"))

        result = subprocess.run(args, cwd=cwd, check=False,
                                capture_output=True)

        if result.returncode != 0:
            print_error("Command failed with return code %d" % result.returncode)
            return False

        return True
    except FileNotFoundError:
        print_error("Command not found: %s" % command)
        return False
    except Exception as e:
        print_error("Error running command: %s" % str(e))
        return False


def check_command_exists(command):
    """
    Checks if a command exists effectively by trying to find it.
    """
    from shutil import which
    return which(command) is not None
