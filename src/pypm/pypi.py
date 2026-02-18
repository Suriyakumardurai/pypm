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



# Memory cache for current execution
_METADATA_MEMORY_CACHE = {}

def get_pypi_metadata(package_name: str) -> Optional[dict]:
    """
    Fetches and caches PyPI metadata for a package.
    """
    clean_name = package_name.split("[")[0].lower()
    
    # 1. Check Memory Cache
    if clean_name in _METADATA_MEMORY_CACHE:
        return _METADATA_MEMORY_CACHE[clean_name]
        
    # 2. Check Disk Cache (Support legacy bool and new dict)
    if clean_name in _PACKAGE_CACHE:
        cached_val = _PACKAGE_CACHE[clean_name]
        if isinstance(cached_val, dict) and "info" in cached_val:
            _METADATA_MEMORY_CACHE[clean_name] = cached_val
            return cached_val
        # If bool or old format, we ignore and fetch fresh to populate cache
    
    url = f"https://pypi.org/pypi/{clean_name}/json"
    req = urllib.request.Request(url, headers={"User-Agent": "pypm-cli/0.0.2"})
    
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                
                # Slim down data to save disk space?
                # For now save full or at least key fields
                # Storing full json is safe for now.
                
                _METADATA_MEMORY_CACHE[clean_name] = data
                _PACKAGE_CACHE[clean_name] = data
                save_cache(_PACKAGE_CACHE)
                
                return data
    except urllib.error.HTTPError as e:
        if e.code == 404:
            _METADATA_MEMORY_CACHE[clean_name] = None
            _PACKAGE_CACHE[clean_name] = False # Explicit False for not found
            save_cache(_PACKAGE_CACHE)
            return None
    except Exception as e:
        log(f"Error fetching metadata for {clean_name}: {e}", level="DEBUG")
        
    return None

def check_package_exists(package_name: str) -> bool:
    """
    Checks if a package exists on PyPI.
    """
    clean_name = package_name.split("[")[0].lower()
    
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



def get_latest_version(package_name: str) -> Optional[str]:
    """
    Fetches the latest version of a package from PyPI.
    """
    data = get_pypi_metadata(package_name)
    if data:
        return data["info"]["version"]
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

def get_package_extras(package_name: str) -> dict:
    """
    Fetches the extras for a package from PyPI.
    Returns a dict mapping extra names to their requirements.
    This is a simplified version; mapped extras logic will be in resolver.
    Actually, we need to know WHICH extra provides a certain module.
    PyPI metadata `requires_dist` looks like:
    "requires_dist": [
        "boto3 (>=1.0.0) ; extra == 'aws'",
        "google-cloud-storage ; extra == 'gcp'"
    ]
    BUT, this tells us what dependencies an extra PULS IN.
    It does NOT tell us what modules are provided by the package itself when that extra is installed.
    
    Wait. `from pipecat import aws` -> `pipecat-ai[aws]`.
    The user implies that the submodule `aws` is enabled by the extra `aws`.
    This is a convention. PyPI metadata does NOT store "module X is provided by extra Y".
    However, often the extra name MATCHES the submodule name.
    
    So we need to fetch the LIST of valid extras for a package.
    """
    data = get_pypi_metadata(package_name)
    extras = set()
    
    if data:
        # Parse requires_dist to find all unique extra markers
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
