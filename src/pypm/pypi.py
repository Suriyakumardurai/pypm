import urllib.request
from typing import Optional
import urllib.error
import json
from pathlib import Path
from .utils import log

# Cache Setup
CACHE_DIR = Path.home() / ".cache" / "pypm"
CACHE_FILE = CACHE_DIR / "cache.json"

def load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_cache(cache: dict):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception as e:
        log(f"Failed to save cache: {e}", level="DEBUG")

# Global Cache
_PACKAGE_CACHE = load_cache()

def check_package_exists(package_name: str) -> bool:
    """
    Checks if a package exists on PyPI using the JSON API.
    Uses usage of local cache to avoid redundant network requests.
    """
    if package_name in _PACKAGE_CACHE:
        return _PACKAGE_CACHE[package_name]

    url = f"https://pypi.org/pypi/{package_name}/json"
    exists = False
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            if response.status == 200:
                exists = True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            exists = False
        else:
            log(f"Error checking PyPI for {package_name}: {e}", level="DEBUG")
            # Don't cache errors other than 404
            return False 
    except Exception as e:
        log(f"Network error checking PyPI for {package_name}: {e}", level="DEBUG")
        return False
    
    # Update Cache
    _PACKAGE_CACHE[package_name] = exists
    save_cache(_PACKAGE_CACHE)
    return exists



def get_latest_version(package_name: str) -> Optional[str]:
    """
    Fetches the latest version of a package from PyPI.
    Returns the version string (e.g., "1.0.0") or None if not found.
    """
    clean_name = package_name.split("[")[0]
    
    # We could cache versions too, but versions change. 
    # For now, let's strictly cache existence. Version fetching is rarer (only on install?).
    # Actually, let's trust the network for versions to be fresh.
    
    url = f"https://pypi.org/pypi/{clean_name}/json"
    req = urllib.request.Request(url, headers={"User-Agent": "pypm-cli/0.0.1"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return data["info"]["version"]
    except Exception as e:
        log(f"Failed to fetch version for {package_name}: {e}", level="DEBUG")
    return None

def find_pypi_package(import_name: str) -> Optional[str]:
    """
    Attempts to find the correct PyPI package name for a given import.
    """
    # 1. Exact match
    if check_package_exists(import_name):
        return import_name
        
    # 2. Common patterns
    variations = [
        f"python-{import_name}",
        f"{import_name}-python",
        f"py{import_name}",
        f"{import_name}py",
        f"py-{import_name}"
    ]
    
    for variant in variations:
        if check_package_exists(variant):
            return variant
            
    return None
