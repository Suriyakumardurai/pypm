import os
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
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

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


def get_optimal_workers(n_tasks, io_bound=False):
    # type: (int, bool) -> int
    """
    Computes optimal thread pool size based on system resources.
    Memory-aware: avoids overwhelming low-RAM systems (4GB).
    Reduces thread stack size to 256KB (from default 8MB) for massive memory savings.
    """
    import threading as _threading

    # Reduce thread stack size on first call (256KB instead of default 8MB)
    # 128 threads: 8MB default = 1GB stacks. 256KB = 32MB stacks.
    try:
        _threading.stack_size(256 * 1024)
    except (ValueError, RuntimeError):
        pass  # Some platforms don't support stack_size

    cpu = os.cpu_count() or 4

    # Memory-aware cap: detect available RAM
    mem_cap = 128  # default max
    try:
        if sys.platform == "win32":
            # Windows: use ctypes to get available physical memory
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            mem_status = MEMORYSTATUSEX()
            mem_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status))
            avail_mb = mem_status.ullAvailPhys // (1024 * 1024)
        else:
            # Linux/macOS: read /proc/meminfo or use os.sysconf
            try:
                pages = os.sysconf("SC_AVPHYS_PAGES")  # type: ignore[attr-defined]
                page_size = os.sysconf("SC_PAGE_SIZE")  # type: ignore[attr-defined]
                avail_mb = (pages * page_size) // (1024 * 1024)
            except (ValueError, AttributeError):
                avail_mb = 4096  # Assume 4GB if can't detect

        # Scale workers based on available memory
        # Each thread with 256KB stack + overhead ≈ 512KB
        # Reserve 512MB for the process itself
        usable_mb = max(256, avail_mb - 512)
        mem_cap = max(4, usable_mb // 1)  # ~1MB per thread (stack + objects)

    except Exception:
        mem_cap = 64  # Conservative fallback

    if io_bound:
        max_w = min(cpu * 12, 128, mem_cap)
    else:
        max_w = min(cpu * 2, 32, mem_cap)

    return max(1, min(max_w, n_tasks))
