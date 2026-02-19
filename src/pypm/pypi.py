import urllib.request
import urllib.error
import json
import os
import stat
import re
from pathlib import Path  # noqa: F401
from typing import Optional, Dict, List, Any  # noqa: F401
from .utils import log

# Cache Setup
CACHE_DIR = Path.home() / ".cache" / "pypm"
CACHE_FILE = CACHE_DIR / "cache.json"

# Security: Valid PyPI package name pattern (PEP 508)
_VALID_PYPI_NAME_RE = re.compile(r'^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$')

# Characters that must never appear in URL path segments
_URL_UNSAFE_RE = re.compile(r'[/\\?#&=@:;{}\[\]|^~`\s]')


def _sanitize_package_name(name):
    # type: (str) -> Optional[str]
    """
    Validates and sanitizes a package name for use in PyPI API URLs.
    Returns the sanitized name or None if the name is invalid/dangerous.
    """
    if not name or len(name) > 200:
        return None

    # Strip extras and version specifiers for URL purposes
    clean = name.split("[")[0].split("=")[0].split("<")[0].split(">")[0].split("!")[0].strip()

    if not clean:
        return None

    # Reject path traversal attempts
    if ".." in clean or clean.startswith("/") or clean.startswith("\\"):
        return None

    # Reject URL-unsafe characters
    if _URL_UNSAFE_RE.search(clean):
        return None

    return clean.lower()


def _validate_cache_entry(entry):
    # type: (Any) -> bool
    """
    Validates that a cache entry has the expected structure.
    """
    if isinstance(entry, bool):
        return True  # Legacy bool entries (True/False for exists/not-exists)
    if isinstance(entry, dict):
        # Must have 'info' key with at least 'name' for valid PyPI metadata
        if "info" in entry and isinstance(entry["info"], dict):
            return "name" in entry["info"]
    return False


def _set_secure_permissions(filepath):
    # type: (Path) -> None
    """
    Sets restrictive file permissions (owner read/write only) on cache files.
    """
    try:
        if os.name != "nt":  # Unix-like systems
            os.chmod(str(filepath), stat.S_IRUSR | stat.S_IWUSR)  # 600
    except OSError:
        pass  # Best effort


def load_cache():
    # type: () -> dict
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(str(CACHE_FILE), "r") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            log("Cache file corrupted (not a dict), resetting.", level="DEBUG")
            return {}

        # Validate each entry
        validated = {}
        for key, val in data.items():
            if _validate_cache_entry(val):
                validated[key] = val
            else:
                log("Removed invalid cache entry: %s" % key, level="DEBUG")

        return validated
    except (json.JSONDecodeError, ValueError):
        log("Cache file corrupted, resetting.", level="DEBUG")
        return {}
    except Exception:
        return {}

def save_cache(cache):
    # type: (dict) -> None
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Set directory permissions (700 on Unix)
        _set_secure_permissions(CACHE_DIR)

        with open(str(CACHE_FILE), "w") as f:
            json.dump(cache, f)

        # Set file permissions (600 on Unix)
        _set_secure_permissions(CACHE_FILE)
    except Exception as e:
        log("Failed to save cache: %s" % str(e), level="DEBUG")

# Global Cache
_PACKAGE_CACHE = load_cache()


# Memory cache for current execution
_METADATA_MEMORY_CACHE = {}  # type: Dict[str, Any]

def get_pypi_metadata(package_name):
    # type: (str) -> Optional[dict]
    """
    Fetches and caches PyPI metadata for a package.
    """
    clean_name = _sanitize_package_name(package_name)
    if clean_name is None:
        log("Rejected invalid package name: %s" % package_name, level="DEBUG")
        return None

    # 1. Check Memory Cache
    if clean_name in _METADATA_MEMORY_CACHE:
        return _METADATA_MEMORY_CACHE[clean_name]

    # 2. Check Disk Cache (Support legacy bool and new dict)
    if clean_name in _PACKAGE_CACHE:
        cached_val = _PACKAGE_CACHE[clean_name]
        if isinstance(cached_val, dict) and "info" in cached_val:
            _METADATA_MEMORY_CACHE[clean_name] = cached_val
            return cached_val

    # Security: URL is safe because clean_name is validated
    url = "https://pypi.org/pypi/%s/json" % clean_name
    req = urllib.request.Request(url, headers={"User-Agent": "pypm-cli/0.0.5"})

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                raw_data = response.read()
                # Security: Limit response size to 5MB to prevent DoS
                if len(raw_data) > 5 * 1024 * 1024:
                    log("Response too large for %s, skipping." % clean_name, level="DEBUG")
                    return None

                data = json.loads(raw_data.decode("utf-8"))

                # Validate response structure
                if not isinstance(data, dict) or "info" not in data:
                    log("Invalid API response for %s" % clean_name, level="DEBUG")
                    return None

                _METADATA_MEMORY_CACHE[clean_name] = data
                _PACKAGE_CACHE[clean_name] = data
                save_cache(_PACKAGE_CACHE)

                return data
    except urllib.error.HTTPError as e:
        if e.code == 404:
            _METADATA_MEMORY_CACHE[clean_name] = None
            _PACKAGE_CACHE[clean_name] = False  # Explicit False for not found
            save_cache(_PACKAGE_CACHE)
            return None
    except Exception as e:
        log("Error fetching metadata for %s: %s" % (clean_name, str(e)), level="DEBUG")

    return None

def check_package_exists(package_name):
    # type: (str) -> bool
    """
    Checks if a package exists on PyPI.
    """
    clean_name = _sanitize_package_name(package_name)
    if clean_name is None:
        return False

    # Check simple cache first
    if clean_name in _PACKAGE_CACHE:
        val = _PACKAGE_CACHE[clean_name]
        if isinstance(val, bool):
            return val
        if isinstance(val, dict):
            return True

    # Fetch metadata
    data = get_pypi_metadata(clean_name)
    return data is not None



def get_latest_version(package_name):
    # type: (str) -> Optional[str]
    """
    Fetches the latest version of a package from PyPI.
    """
    data = get_pypi_metadata(package_name)
    if data:
        return data["info"]["version"]
    return None

def find_pypi_package(import_name):
    # type: (str) -> Optional[str]
    """
    Attempts to find the correct PyPI package name for a given import.
    """
    # 1. Exact match
    if check_package_exists(import_name):
        return import_name

    # 2. Common patterns
    variations = [
        "python-%s" % import_name,
        "%s-python" % import_name,
        "py%s" % import_name,
        "%spy" % import_name,
        "py-%s" % import_name,
    ]

    for variant in variations:
        if check_package_exists(variant):
            return variant

    return None

def get_package_extras(package_name):
    # type: (str) -> List[str]
    """
    Fetches the extras for a package from PyPI.
    """
    data = get_pypi_metadata(package_name)
    extras = set()

    if data:
        requires_dist = data["info"].get("requires_dist", [])
        if requires_dist:
            for dist in requires_dist:
                if "; extra ==" in dist:
                    try:
                        part = dist.split("extra ==")[1]
                        part = part.strip().strip("'").strip('"')
                        if " " in part:
                            part = part.split(" ")[0].strip("'").strip('"')
                        extras.add(part)
                    except IndexError:
                        pass

    return list(extras)
