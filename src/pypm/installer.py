import re
import sys
from typing import List  # noqa: F401

from .utils import check_command_exists, log, print_error, run_command

# PEP 508 compliant package name pattern (letters, digits, hyphens, underscores, dots, extras, version specs)
_SAFE_PACKAGE_RE = re.compile(
    r'^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?'  # base name
    r'(\[[A-Za-z0-9,_ -]+\])?'                       # optional extras
    r'([<>=!~]+[A-Za-z0-9.*]+)?$'                     # optional version spec
)

# Characters that MUST NEVER appear in a package spec passed to shell
_SHELL_METACHAR_RE = re.compile(r'[;&|`$(){}!\\\'"\n\r\t]')


def _is_safe_package_name(name):
    # type: (str) -> bool
    """
    Validates that a package name/spec is safe to pass to pip/uv.
    Rejects any string containing shell metacharacters or suspicious patterns.
    """
    if not name or len(name) > 200:
        return False

    # Reject shell metacharacters
    if _SHELL_METACHAR_RE.search(name):
        return False

    # Must match PEP 508-ish pattern
    if not _SAFE_PACKAGE_RE.match(name):
        return False

    return True


def install_packages(packages):
    # type: (List[str]) -> bool
    """
    Installs packages using uv if available, otherwise pip.
    All package names are validated before being passed to the shell.
    """
    if not packages:
        log("No packages to install.", level="INFO")
        return True

    # Security: Validate every package name before constructing shell command
    safe_packages = []
    rejected = []
    for pkg in packages:
        if _is_safe_package_name(pkg):
            safe_packages.append(pkg)
        else:
            rejected.append(pkg)

    if rejected:
        print_error(
            "Rejected %d unsafe package name(s): %s"
            % (len(rejected), ", ".join(rejected))
        )
        log("These names contain invalid characters and were skipped for safety.", level="WARNING")

    if not safe_packages:
        log("No valid packages to install after validation.", level="WARNING")
        return False

    use_uv = check_command_exists("uv")

    if use_uv:
        log("Found uv, using it for installation...", level="INFO")
        command_str = "uv pip install "
        # Check if running in venv
        if sys.prefix == sys.base_prefix:
            log("No virtual environment detected, using --system for uv.", level="WARNING")
            command_str += "--system "
        command_str += " ".join(safe_packages)
    else:
        log("uv not found, falling back to pip...", level="INFO")
        command_str = "%s -m pip install %s" % (sys.executable, " ".join(safe_packages))

    log("Installing: %s" % ", ".join(safe_packages), level="DEBUG")
    if run_command(command_str):
        log("Successfully installed packages.", level="DEBUG")
        return True
    else:
        log("Failed to install packages.", level="ERROR")
        return False
