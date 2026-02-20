import json
import os
import stat
import re
import threading
from pathlib import Path  # noqa: F401
from typing import Optional, Dict, List, Any  # noqa: F401
from .utils import log

# ---------- Cache Setup ----------
CACHE_DIR = Path.home() / ".cache" / "pypm"
CACHE_FILE = CACHE_DIR / "cache.json"

# Security: Valid PyPI package name pattern (PEP 508)
_VALID_PYPI_NAME_RE = re.compile(r'^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$')

# Characters that must never appear in URL path segments
_URL_UNSAFE_RE = re.compile(r'[/\\?#&=@:;{}\[\]|^~`\s]')

# Lock only for writes (CPython GIL protects dict reads)
_WRITE_LOCK = threading.Lock()

# Flag to track if cache is dirty (needs flushing)
_CACHE_DIRTY = False


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
    if isinstance(entry, bool):
        return True
    if isinstance(entry, dict):
        if "info" in entry and isinstance(entry["info"], dict):
            return "name" in entry["info"]
    return False


def _set_secure_permissions(filepath):
    # type: (Path) -> None
    try:
        if os.name != "nt":
            os.chmod(str(filepath), stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _slim_metadata(data):
    # type: (dict) -> dict
    """
    Strips PyPI metadata to only essential fields.
    Full JSON can be 500KB-2MB per package. We only need ~200 bytes.
    """
    info = data.get("info", {})
    return {
        "info": {
            "name": info.get("name", ""),
            "version": info.get("version", ""),
            "requires_dist": info.get("requires_dist"),
        }
    }


def load_cache():
    # type: () -> dict
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(str(CACHE_FILE), "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        validated = {}
        for key, val in data.items():
            if _validate_cache_entry(val):
                validated[key] = val
        return validated
    except (json.JSONDecodeError, ValueError):
        return {}
    except Exception:
        return {}


def save_cache(cache):
    # type: (dict) -> None
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _set_secure_permissions(CACHE_DIR)
        with open(str(CACHE_FILE), "w") as f:
            json.dump(cache, f, separators=(",", ":"))  # Compact JSON
        _set_secure_permissions(CACHE_FILE)
    except Exception as e:
        log("Failed to save cache: %s" % str(e), level="DEBUG")


# Global Cache
_PACKAGE_CACHE = load_cache()

# Memory cache for current execution (lock-free reads under GIL)
_METADATA_MEMORY_CACHE = {}  # type: Dict[str, Any]

# Pre-sanitized name cache to avoid redundant sanitization
_SANITIZE_CACHE = {}  # type: Dict[str, Optional[str]]


def _sanitize_cached(name):
    # type: (str) -> Optional[str]
    """Cached version of _sanitize_package_name — avoids re-splitting/re-checking."""
    result = _SANITIZE_CACHE.get(name)
    if result is not None:
        return result
    # None could mean "not cached" or "invalid". Use sentinel.
    if name in _SANITIZE_CACHE:
        return None
    result = _sanitize_package_name(name)
    _SANITIZE_CACHE[name] = result
    return result


# ---------- HTTP Session (Connection Pooling) ----------
_SESSION = None  # type: Any
_HAS_REQUESTS = False

try:
    import requests as _requests_mod
    from requests.adapters import HTTPAdapter
    _HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    _HAS_REQUESTS = False


def _get_session():
    # type: () -> Any
    """Returns a shared requests.Session with connection pooling configured."""
    global _SESSION
    if _SESSION is None and _HAS_REQUESTS:
        _SESSION = _requests_mod.Session()
        _SESSION.headers.update({"User-Agent": "pypm-cli/0.0.6"})
        adapter = HTTPAdapter(
            pool_connections=20,
            pool_maxsize=128,
            max_retries=1,
        )
        _SESSION.mount("https://", adapter)
        _SESSION.mount("http://", adapter)
    return _SESSION


def _mark_dirty():
    # type: () -> None
    global _CACHE_DIRTY
    _CACHE_DIRTY = True


def flush_cache():
    # type: () -> None
    """Flush in-memory cache to disk. Called once at end of resolution."""
    global _CACHE_DIRTY
    with _WRITE_LOCK:
        if _CACHE_DIRTY:
            save_cache(_PACKAGE_CACHE)
            _CACHE_DIRTY = False


def get_pypi_metadata(package_name):
    # type: (str) -> Optional[dict]
    """
    Fetches and caches PyPI metadata for a package.
    Stores only slim metadata (name, version, requires_dist) to save memory.
    """
    clean_name = _sanitize_cached(package_name)
    if clean_name is None:
        return None

    # 1. Lock-free read from memory cache (GIL-safe)
    cached = _METADATA_MEMORY_CACHE.get(clean_name)
    if cached is not None:
        return cached
    # Check if explicitly cached as None (not found)
    if clean_name in _METADATA_MEMORY_CACHE:
        return None

    # 2. Lock-free read from disk cache
    disk_val = _PACKAGE_CACHE.get(clean_name)
    if disk_val is not None:
        if isinstance(disk_val, dict) and "info" in disk_val:
            _METADATA_MEMORY_CACHE[clean_name] = disk_val
            return disk_val
        if disk_val is False:
            _METADATA_MEMORY_CACHE[clean_name] = None
            return None

    # 3. Fetch from PyPI
    url = "https://pypi.org/pypi/%s/json" % clean_name
    data = None

    session = _get_session()

    if session is not None:
        try:
            resp = session.get(url, timeout=3)
            if resp.status_code == 200:
                raw_data = resp.content
                if len(raw_data) > 5 * 1024 * 1024:
                    return None
                data = resp.json()
            elif resp.status_code == 404:
                with _WRITE_LOCK:
                    _METADATA_MEMORY_CACHE[clean_name] = None
                    _PACKAGE_CACHE[clean_name] = False
                    _mark_dirty()
                return None
        except Exception as e:
            log("Error fetching %s: %s" % (clean_name, str(e)), level="DEBUG")
            return None
    else:
        req = urllib.request.Request(url, headers={"User-Agent": "pypm-cli/0.0.6"})
        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                if response.status == 200:
                    raw_data = response.read()
                    if len(raw_data) > 5 * 1024 * 1024:
                        return None
                    data = json.loads(raw_data.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                with _WRITE_LOCK:
                    _METADATA_MEMORY_CACHE[clean_name] = None
                    _PACKAGE_CACHE[clean_name] = False
                    _mark_dirty()
                return None
        except Exception as e:
            log("Error fetching %s: %s" % (clean_name, str(e)), level="DEBUG")
            return None

    # Validate, slim down, and cache
    if data is not None and isinstance(data, dict) and "info" in data:
        slim = _slim_metadata(data)
        with _WRITE_LOCK:
            _METADATA_MEMORY_CACHE[clean_name] = slim
            _PACKAGE_CACHE[clean_name] = slim
            _mark_dirty()
        return slim

    return None


def check_package_exists(package_name):
    # type: (str) -> bool
    """Checks if a package exists on PyPI. Uses GET to populate cache."""
    clean_name = _sanitize_cached(package_name)
    if clean_name is None:
        return False

    # Lock-free cache reads (GIL-safe)
    if clean_name in _METADATA_MEMORY_CACHE:
        return _METADATA_MEMORY_CACHE[clean_name] is not None
    cached = _PACKAGE_CACHE.get(clean_name)
    if cached is not None:
        if isinstance(cached, bool):
            return cached
        return True

    data = get_pypi_metadata(clean_name)
    return data is not None


def check_package_exists_head(package_name):
    # type: (str) -> bool
    """
    Fast existence-only check using HTTP HEAD (no body download).
    ~10x faster than full GET. Used for variation probing.
    """
    clean_name = _sanitize_cached(package_name)
    if clean_name is None:
        return False

    # Lock-free cache reads
    if clean_name in _METADATA_MEMORY_CACHE:
        return _METADATA_MEMORY_CACHE[clean_name] is not None
    cached = _PACKAGE_CACHE.get(clean_name)
    if cached is not None:
        if isinstance(cached, bool):
            return cached
        return True

    url = "https://pypi.org/pypi/%s/json" % clean_name
    session = _get_session()

    if session is not None:
        try:
            resp = session.head(url, timeout=2, allow_redirects=True)
            exists = resp.status_code == 200
            with _WRITE_LOCK:
                if not exists:
                    _METADATA_MEMORY_CACHE[clean_name] = None
                    _PACKAGE_CACHE[clean_name] = False
                    _mark_dirty()
            return exists
        except Exception:
            pass
    else:
        return check_package_exists(package_name)

    return False


def get_latest_version(package_name):
    # type: (str) -> Optional[str]
    data = get_pypi_metadata(package_name)
    if data:
        return data["info"]["version"]
    return None


def find_pypi_package(import_name):
    # type: (str) -> Optional[str]
    """
    Attempts to find the correct PyPI package name for a given import.
    Uses HEAD requests for fast existence checks on variations.
    """
    if check_package_exists(import_name):
        return import_name

    variations = [
        "python-%s" % import_name,
        "%s-python" % import_name,
        "py%s" % import_name,
        "%spy" % import_name,
        "py-%s" % import_name,
    ]

    for variant in variations:
        if check_package_exists_head(variant):
            return variant

    return None


def get_package_extras(package_name):
    # type: (str) -> List[str]
    data = get_pypi_metadata(package_name)
    extras = set()

    if data:
        requires_dist = data["info"].get("requires_dist") or []
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
