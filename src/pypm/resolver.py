import sys
from typing import Optional, Dict, List, Any, Set  # noqa: F401

from .db import KNOWN_PYPI_PACKAGES
from .pypi import check_package_exists, find_pypi_package, flush_cache
from .utils import get_optimal_workers, log

# --- importlib.metadata compatibility ---
try:
    import importlib.metadata as _importlib_metadata  # novm
except ImportError:
    try:
        import importlib_metadata as _importlib_metadata  # type: ignore[no-redef,import-untyped,import-not-found]
    except ImportError:
        _importlib_metadata = None  # type: ignore[assignment]

# Load standard library module names
if sys.version_info >= (3, 10):
    STDLIB_MODULES = sys.stdlib_module_names  # novm
else:
    # Python < 3.10 fallback — comprehensive stdlib list
    # Covers all public modules present in Python 3.5–3.9
    STDLIB_MODULES = frozenset({
        # Core / Built-in
        "os", "sys", "re", "math", "random", "datetime", "json", "logging",
        "argparse", "subprocess", "typing", "pathlib", "collections", "itertools",
        "functools", "ast", "shutil", "time", "io", "copy", "platform", "enum",
        "threading", "multiprocessing", "socket", "email", "http", "urllib",
        "dataclasses", "contextlib", "abc", "inspect", "warnings", "traceback",
        # String / Text
        "string", "textwrap", "unicodedata", "codecs", "difflib", "gettext",
        "locale", "readline",
        # Data types
        "struct", "array", "queue", "heapq", "bisect", "operator",
        "decimal", "fractions", "numbers", "statistics",
        # File / OS
        "glob", "tempfile", "fnmatch", "stat", "fileinput", "filecmp",
        "os.path", "posixpath", "ntpath",
        # Compression / Archive
        "zipfile", "tarfile", "gzip", "bz2", "lzma", "zlib",
        # Cryptography / Hashing
        "hashlib", "hmac", "secrets",
        # Database
        "sqlite3", "dbm", "shelve",
        # CSV / Config
        "csv", "configparser", "tomllib",
        # Internet protocols
        "ftplib", "imaplib", "smtplib", "poplib", "xmlrpc",
        "html", "xml", "webbrowser", "cgi", "cgitb",
        # Concurrency
        "asyncio", "concurrent", "selectors", "signal", "mmap",
        "sched",
        # Debugging / Profiling
        "pdb", "cProfile", "profile", "pstats", "timeit", "trace",
        "dis", "code", "codeop",
        # Token / Parsing
        "token", "tokenize", "keyword", "symbol",
        # Import system
        "importlib", "pkgutil", "zipimport",
        # Testing
        "unittest", "doctest",
        # Type / Runtime
        "types", "weakref", "gc", "atexit", "builtins",
        # Binary / Marshal
        "pickle", "copyreg", "marshal", "base64", "binascii",
        "quopri", "uu",
        # Misc
        "pprint", "reprlib", "contextlib", "graphlib",
        "ipaddress", "uuid", "getpass", "netrc",
        "errno", "ctypes", "sysconfig", "site",
        # Multimedia
        "wave", "audioop", "colorsys", "imghdr", "sndhdr",
        # Markup
        "html.parser", "xml.etree", "xml.dom", "xml.sax",
        # Encoding
        "encodings", "chardet",
        # Windows-specific (present but may not be usable on *nix)
        "winreg", "winsound", "msvcrt", "msilib",
        # Unix-specific
        "fcntl", "grp", "pwd", "resource", "termios", "tty", "pty",
        "posix", "syslog",
        # tkinter
        "tkinter", "turtle",
        # Other stdlib
        "mailbox", "mimetypes", "optparse", "formatter",
    })

# Common import name -> PyPI package name mappings
# Kept as a fast-path cache for known non-obvious mappings
COMMON_MAPPINGS = {
    "sklearn": "scikit-learn",
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "jose": "python-jose[cryptography]",
    "barcode": "python-barcode",
    "pydantic_settings": "pydantic-settings",
    "mysqldb": "mysqlclient",
    "MySQLdb": "mysqlclient",
    "dotenv": "python-dotenv",
    "dateutil": "python-dateutil",
    "psycopg2": "psycopg2-binary",
    "tls_client": "tls-client",
    "google.protobuf": "protobuf",
    "telegram": "python-telegram-bot",
    "mysql": "pymysql",
    "qrcode": "qrcode[pil]",
    "pipecat": "pipecat-ai",
    "pypm": "pypm-cli",
    # Classic Traps
    "serial": "pyserial",
    "jwt": "PyJWT",
    "dns": "dnspython",
    "websocket": "websocket-client",
    "pkg_resources": "setuptools",
    # Extended mappings (edge cases)
    "attr": "attrs",
    "attrs": "attrs",
    "gi": "PyGObject",
    "Crypto": "pycryptodome",
    "Cryptodome": "pycryptodome",
    "wx": "wxPython",
    "magic": "python-magic",
    "usb": "pyusb",
    "socks": "PySocks",
    "bson": "pymongo",
    "kafka": "kafka-python",
    "zmq": "pyzmq",
    "nacl": "PyNaCl",
    "skimage": "scikit-image",
    "docx": "python-docx",
    "pptx": "python-pptx",
    "slugify": "python-slugify",
    "decouple": "python-decouple",
    "colorlog": "colorlog",
    "engineio": "python-engineio",
    "socketio": "python-socketio",
    "git": "GitPython",
    "ldap": "python-ldap",
    "multipart": "python-multipart",
    "lz4": "lz4",
    "snappy": "python-snappy",
    "geopy": "geopy",
    "rtree": "Rtree",
}

# Pre-computed lowercase lookup for O(1) case-insensitive matching
COMMON_MAPPINGS_LOWER = {k.lower(): v for k, v in COMMON_MAPPINGS.items()}

# Framework specific additions (if key is found, add value)
FRAMEWORK_EXTRAS = {
    "fastapi": ["uvicorn[standard]", "python-multipart", "email-validator"],
    "flask": ["gunicorn"],
    "django": ["gunicorn", "psycopg2-binary"],
    "celery": ["redis"],
    "passlib": ["passlib[bcrypt]", "bcrypt==4.1.2"],
    "sqlalchemy": ["greenlet"],
    "pandas": ["openpyxl"],
    "uvicorn": ["uvicorn[standard]"],
}

def is_stdlib(module_name):
    """
    Checks if a module is in the standard library.
    """
    if module_name.startswith("_"):
        return True

    base_module = module_name.split(".")[0]
    return base_module in STDLIB_MODULES



# Packages that exist on PyPI but are almost always local modules or namespace roots in user projects
SUSPICIOUS_PACKAGES = {
    # Generic project structure names
    "core", "modules", "crm", "ledgers", "config", "utils", "common",
    "tests", "test", "settings", "db", "database",
    "app", "main", "base", "api", "infra", "lib", "libs", "helpers",
    "models", "schemas", "services", "controllers", "routers",
    "middleware", "plugins", "extensions", "tasks", "jobs",
    "views", "forms", "serializers", "signals", "admin", "management",
    "fixtures", "migrations", "templatetags", "context_processors",
    # Cloud namespace roots (actual packages use submodules like google.cloud.storage)
    "google", "azure", "amazon", "aws",
    # Common project names that also exist on PyPI
    "setup", "manage", "server", "worker", "run", "start",
}

def get_installed_version(package_name):
    """
    Attempts to get the installed version of a package.
    Returns the package name with version specifier if found, else just package name.
    """
    if _importlib_metadata is None:
        return package_name

    # Clean package name for lookup (remove extras)
    clean_name = package_name.split("[")[0]
    try:
        version = _importlib_metadata.version(clean_name)
        return "%s==%s" % (package_name, version)
    except Exception:
        return package_name

def resolve_dependencies(imports, project_root, known_local_modules=None):
    """
    Resolves imports to distribution packages using Online PyPI verification.
    Uses batch set operations for stdlib/local filtering (O(1) amortized).
    """
    dependencies = []

    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Prepare filtering sets
    if known_local_modules is None:
        known_local_modules = set()

    # ---- BATCH FILTER: stdlib + local + suspicious (set operations) ----
    # Build lowercase stdlib set for case-insensitive matching
    stdlib_lower = frozenset(m.lower() for m in STDLIB_MODULES)

    # Pre-compute base modules and filter in bulk
    candidates_to_check = []
    resolved_bases = set()
    seen_bases = set()

    for module in imports:
        module_lower = module.lower()
        base_module = module.split(".")[0]

        # 1. Batch stdlib filter (O(1) set lookup)
        if module in STDLIB_MODULES or module_lower in stdlib_lower:
            continue
        if base_module in STDLIB_MODULES or base_module.lower() in stdlib_lower:
            continue

        # 2. Local module filter
        if base_module in known_local_modules:
            continue

        # 3. Suspicious names filter
        if module in SUSPICIOUS_PACKAGES:
            continue

        # 4. Fast Path: Common Mappings (O(1) lookup via pre-computed lowercase dict)
        module_lower = module.lower()
        if module in COMMON_MAPPINGS:
            dependencies.append(COMMON_MAPPINGS[module])
            resolved_bases.add(module_lower.replace("_", "-"))
            continue

        mapped = COMMON_MAPPINGS_LOWER.get(module_lower)
        if mapped is not None:
            dependencies.append(mapped)
            resolved_bases.add(module_lower.replace("_", "-"))
            continue

        # 5. Fast Path: Known Packages
        norm_module_name = module_lower.replace("_", "-").replace(".", "-")

        if norm_module_name in KNOWN_PYPI_PACKAGES:
             dependencies.append(norm_module_name)
             resolved_bases.add(norm_module_name)
             continue

        if module_lower in KNOWN_PYPI_PACKAGES:
             dependencies.append(module_lower)
             resolved_bases.add(module_lower)
             continue

        # 6. Queue for Online Check (deduplicate by base module)
        base_part = module.split(".")[0].lower().replace("_", "-")
        if base_part in resolved_bases and "." in module:
            continue
        if base_part in seen_bases:
            continue
        seen_bases.add(base_part)

        candidates_to_check.append(module)

    # 5. Online Verification (Parallelized for speed)
    if candidates_to_check:
        from .pypi import get_package_extras
        from .utils import print_step

        verified_deps = set()

        def processing_task(module):
            # Try 1: Known Namespace Package?
            hyphenated = module.lower().replace("_", "-").replace(".", "-")
            if hyphenated in KNOWN_PYPI_PACKAGES:
                return hyphenated, None

            # Try 2: Exact Match
            if check_package_exists(module):
                return module, None

            # Try 3: Base Module Match
            if "." in module:
                base = module.split(".")[0]

                # Check base in KNOWN_PYPI_PACKAGES
                norm_base = base.lower().replace("_", "-")
                if norm_base in KNOWN_PYPI_PACKAGES:
                    return norm_base, None

                # O(1) check via pre-computed lowercase dict
                base_pkg = COMMON_MAPPINGS_LOWER.get(base.lower())

                if not base_pkg:
                    if base.lower() not in SUSPICIOUS_PACKAGES:
                        base_pkg = find_pypi_package(base)

                if base_pkg:
                    submodule_suffix = module.split(".")[-1]

                    # Fetch extras for the base package
                    extras = get_package_extras(base_pkg)
                    if submodule_suffix in extras:
                        return "%s[%s]" % (base_pkg, submodule_suffix), None
                    return base_pkg, None

            # Try 4: Generic Namespace Package check
            if "." in module:
                hyphenated = module.replace(".", "-")
                if check_package_exists(hyphenated):
                    return hyphenated, None

            # Try 5: Common variations (last resort)
            found = find_pypi_package(module)
            if found:
                return found, None

            return None, module

        workers = get_optimal_workers(len(candidates_to_check), io_bound=True)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_module = dict((executor.submit(processing_task, m), m) for m in candidates_to_check)

            for future in as_completed(future_to_module):
                try:
                    result, error_module = future.result()
                    if result:
                        log("Verified '%s' -> '%s'" % (future_to_module[future], result), level="DEBUG")
                        verified_deps.add(result)
                    else:
                        log("Warning: Could not find package for import '%s' on PyPI." % error_module, level="DEBUG")
                except Exception as e:
                    log("Error verifying %s: %s" % (future_to_module[future], str(e)), level="ERROR")

        dependencies.extend(list(verified_deps))

        # Flush cache to disk once after all network checks are done
        flush_cache()

    # 6. Apply Framework Extras
    final_deps = set(dependencies)

    framework_additions = []

    for trigger, extras in FRAMEWORK_EXTRAS.items():
        trace_found = False
        for dep in final_deps:
            if dep.split("[")[0].lower() == trigger.lower():
                trace_found = True
                break

        if trace_found:
            framework_additions.extend(extras)

    if framework_additions:
        from .utils import print_step
        print_step("Detected frameworks, adding extras: %s" % ", ".join(framework_additions))
        final_deps.update(framework_additions)

    # 6b. Deduplicate and Merge Extras
    deps_with_extras = [d for d in final_deps if "[" in d]
    bases_to_remove = set()
    for d in deps_with_extras:
        base = d.split("[")[0]
        bases_to_remove.add(base)

    merged_deps = {}  # type: Dict[str, Dict[str, Any]]

    for dep in final_deps:
        if "[" in dep:
            base = dep.split("[")[0]
            extras_part = dep.split("[")[1].strip("]")
            parsed_extras = set(e.strip() for e in extras_part.split(","))
        else:
            base = dep
            parsed_extras = set()

        version = None
        if "==" in base:
            parts = base.split("==")
            base_name = parts[0]
            version = parts[1]
        else:
            base_name = base

        if base_name not in merged_deps:
            merged_deps[base_name] = {"extras": set(), "version": version}

        merged_deps[base_name]["extras"].update(parsed_extras)
        if version:
             merged_deps[base_name]["version"] = version

    # Reconstruct dependencies
    final_deps_list = []
    for pkg, data in merged_deps.items():
        extras = data["extras"]
        version = data["version"]

        suffix = ""
        if extras:
            sorted_extras = ",".join(sorted(extras))
            suffix = "[%s]" % sorted_extras

        dep_str = "%s%s" % (pkg, suffix)
        if version:
            dep_str += "==%s" % version

        final_deps_list.append(dep_str)

    final_deps = set(final_deps_list)

    # 7. Version Pinning
    pinned_deps = []

    from .utils import check_command_exists

    resolved_map = {}  # type: Dict[str, str]
    uv_success = False

    if check_command_exists("uv") and False:  # Force Disable UV for speed
        pass

    if not uv_success:
        pass

    # Apply resolved versions
    for dep in final_deps:
        clean_name = dep.split("[")[0].lower()

        if clean_name in resolved_map:
            resolved_str = resolved_map[clean_name]
            version = resolved_str.split("==")[1]
            pinned_deps.append("%s==%s" % (dep, version))
        else:
            if "==" in dep:
                 pinned_deps.append(dep)
            else:
                 pinned_deps.append(dep)

    return sorted(list(set(pinned_deps)))
