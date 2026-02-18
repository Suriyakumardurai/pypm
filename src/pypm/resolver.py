import sys
from typing import Set, List
import importlib.metadata

from .utils import log
from .pypi import find_pypi_package, check_package_exists
from .db import KNOWN_PYPI_PACKAGES

# Load standard library module names
if sys.version_info >= (3, 10):
    STDLIB_MODULES = sys.stdlib_module_names
else:
    # Python < 3.10 fallback (simplified list for MVP, expandable)
    # Use frozenset to match sys.stdlib_module_names type
    STDLIB_MODULES = frozenset({
        "os", "sys", "re", "math", "random", "datetime", "json", "logging",
        "argparse", "subprocess", "typing", "pathlib", "collections", "itertools",
        "functools", "ast", "shutil", "time", "io", "copy", "platform", "enum",
        "threading", "multiprocessing", "socket", "email", "http", "urllib",
        "dataclasses", "contextlib", "abc", "inspect", "warnings", "traceback"
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
}

# Framework specific additions (if key is found, add value)
FRAMEWORK_EXTRAS = {
    "fastapi": ["uvicorn[standard]", "python-multipart", "email-validator"],
    "flask": ["gunicorn"],  # Production server suggestion
    "django": ["gunicorn", "psycopg2-binary"], # Common defaults, though implicit detection is better
    "celery": ["redis"], # Common broker
    "passlib": ["passlib[bcrypt]", "bcrypt==4.1.2"], 
    "sqlalchemy": ["greenlet"], 
    "pandas": ["openpyxl"], # Excel support often needed
    "uvicorn": ["uvicorn[standard]"],
}

def is_stdlib(module_name: str) -> bool:
    """
    Checks if a module is in the standard library.
    """
    if module_name.startswith("_"): 
        return True 
        
    base_module = module_name.split(".")[0]
    return base_module in STDLIB_MODULES



# Packages that exist on PyPI but are almost always local modules or namespace roots in user projects
SUSPICIOUS_PACKAGES = {
    "core", "modules", "crm", "ledgers", "config", "utils", "common", "tests", "settings", "db", "database",
    "app", "main", "base", "api", "infra", "models", "schemas", "services", "controllers", "routers",
    "google", "azure", "amazon", "aws"
}

def get_installed_version(package_name: str) -> str:
    """
    Attempts to get the installed version of a package.
    Returns the package name with version specifier if found, else just package name.
    """
    # Clean package name for lookup (remove extras)
    clean_name = package_name.split("[")[0]
    try:
        version = importlib.metadata.version(clean_name)
        return f"{package_name}=={version}"
    except importlib.metadata.PackageNotFoundError:
        return package_name

def resolve_dependencies(imports: Set[str], project_root: str, known_local_modules: Set[str] = None) -> List[str]:
    """
    Resolves imports to distribution packages using Online PyPI verification.
    """
    dependencies = []
    
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Prepare list of candidates to check
    candidates_to_check = []
    
    if known_local_modules is None:
        known_local_modules = set()

    for module in imports:
        # 1. Filter Standard Library
        if is_stdlib(module):
            # log(f"Ignored stdlib module: {module}", level="DEBUG")
            continue
            
        # 1b. Filter Standard Library (LowerCase Check)
        if is_stdlib(module.lower()):
            continue
            
        # 2. Filter Local Modules
        # Pre-calculated check (O(1)) instead of os.walk
        base_module = module.split(".")[0]
        if base_module in known_local_modules:
             log(f"Ignored local module: {module}", level="DEBUG")
             continue
             
        # Optional: Checking specific submodules if needed, but base module check is usually sufficient
        # If `from foo import bar`, module="foo". 
        # If `import foo.bar`, module="foo.bar". Base="foo".
        
        # 3. Filter Suspicious/Generic Names
        if module in SUSPICIOUS_PACKAGES:
             log(f"Ignored suspicious/generic module name: {module} (likely local)", level="DEBUG")
             continue

        # 4. Fast Path: Common Mappings
        if module in COMMON_MAPPINGS:
            dependencies.append(COMMON_MAPPINGS[module])
            continue
            
        # 4b. Fast Path: Common Mappings (Case-Insensitive)
        # Search for mapping where key.lower() == module.lower()
        found_mapping = False
        for m_key, m_val in COMMON_MAPPINGS.items():
            if m_key.lower() == module.lower():
                dependencies.append(m_val)
                found_mapping = True
                break
        if found_mapping:
            continue
            
        # 5. Fast Path: Known Packages (New)
        # Normalize: lower(), replace "_" and "." with "-"
        norm_module_name = module.lower().replace("_", "-").replace(".", "-")
        
        # Check against bundled DB
        if norm_module_name in KNOWN_PYPI_PACKAGES:
             dependencies.append(norm_module_name)
             continue
             
        # Check if "module" (original) is in DB (just in case keys vary)
        if module.lower() in KNOWN_PYPI_PACKAGES:
             dependencies.append(module.lower())
             continue

        # 6. Queue for Online Check
        # Optimization: If the base part of this module is already a known package, 
        # we don't need to check the submodule for online packages unless it's a known namespace.
        # e.g. "fastapi.Depends" -> base "fastapi" is already in dependencies. Skip.
        base_part = module.split(".")[0].lower().replace("_", "-")
        resolved_bases = [d.split("[")[0].lower() for d in dependencies]
        if base_part in resolved_bases and "." in module:
            continue

        candidates_to_check.append(module)
    
    # 5. Online Verification (Parallelized for speed)
    if candidates_to_check:
        from .utils import print_step
        from .pypi import get_package_extras
        # print(f"DEBUG: Candidates to check: {candidates_to_check}")
        # print_step(f"Verifying {len(candidates_to_check)} packages on PyPI...")
        
        # New Resolution Logic:
        # We might have "sklearn.models" and "scikit-learn" (if mapped)
        # We might have "pipecat.aws" and "pipecat"
        
        # We need to map:
        # "sklearn.models" -> "scikit-learn" (via base "sklearn" -> "scikit-learn")
        # "pipecat.aws" -> "pipecat-ai[aws]" (via "pipecat" -> "pipecat-ai", then match "aws" to extra)
        
        verified_deps = set()
        
        def processing_task(module):
            # Try 1: Known Namespace Package? (Strongest signal)
            # e.g. "google.cloud.storage" -> Check if "google-cloud-storage" in DB
            hyphenated = module.lower().replace("_", "-").replace(".", "-")
            if hyphenated in KNOWN_PYPI_PACKAGES:
                return hyphenated, None

            # Try 2: Exact Match
            if check_package_exists(module):
                return module, None
            
            # Try 3: Base Module Match (If it's a known package, prefer it!)
            if "." in module:
                base = module.split(".")[0]
                
                # Check base in KNOWN_PYPI_PACKAGES (New)
                norm_base = base.lower().replace("_", "-")
                if norm_base in KNOWN_PYPI_PACKAGES:
                    # If the base is a known package, we prefer it over any risky hyphenated guesswork
                    # e.g. "fastapi.Depends" -> "fastapi"
                    return norm_base, None

                # Check base in COMMON_MAPPINGS first (Case-Insensitive)
                base_pkg = None
                for m_key, m_val in COMMON_MAPPINGS.items():
                    if m_key.lower() == base.lower():
                        base_pkg = m_val
                        break
                
                if not base_pkg:
                    # Only resolve base package from network if it's fairly unique
                    if base.lower() not in SUSPICIOUS_PACKAGES:
                        base_pkg = find_pypi_package(base)
                
                if base_pkg:
                    # Check if the submodule corresponds to an extra
                    # e.g. module="pipecat.aws", base_pkg="pipecat-ai"
                    submodule_suffix = module.split(".")[-1]
                    
                    # Fetch extras for the base package
                    extras = get_package_extras(base_pkg)
                    if submodule_suffix in extras:
                        return f"{base_pkg}[{submodule_suffix}]", None
                    return base_pkg, None # Just return base if no extra matches
            
            # Try 4: Generic Namespace Package check (Risky)
            # e.g. "somelab.util" -> "somelab-util"
            if "." in module:
                hyphenated = module.replace(".", "-")
                if check_package_exists(hyphenated):
                    return hyphenated, None

            # Try 4: Common variations (last resort)
            found = find_pypi_package(module)
            if found:
                return found, None
                
            return None, module

        with ThreadPoolExecutor(max_workers=50) as executor:
            future_to_module = {executor.submit(processing_task, m): m for m in candidates_to_check}
            
            for future in as_completed(future_to_module):
                try:
                    result, error_module = future.result()
                    if result:
                        log(f"Verified '{future_to_module[future]}' -> '{result}'", level="DEBUG")
                        verified_deps.add(result)
                    else:
                        log(f"Warning: Could not find package for import '{error_module}' on PyPI.", level="DEBUG")
                except Exception as e:
                    log(f"Error verifying {future_to_module[future]}: {e}", level="ERROR")
        
        dependencies.extend(list(verified_deps))
    
    # 6. Apply Framework Extras
    # If specific packages are present, ensure their common companions are added.
    final_deps = set(dependencies)
    
    framework_additions = []
    
    # Check for keys in FRAMEWORK_EXTRAS
    # We need to check if the triggers are in final_deps (names might vary)
    # Simplified check: if any dep contains the key string?
    # No, matching "fastapi" against "fastapi" is safe.
    # But "sqlalchemy" might be "SQLAlchemy" or "sqlalchemy==2.0"?
    # We haven't pinned yet, so it's just names.
    
    for trigger, extras in FRAMEWORK_EXTRAS.items():
        # Check if Trigger is in dependencies.
        # Handle case where dependency is "passlib[bcrypt]" but trigger is "passlib"
        trace_found = False
        for dep in final_deps:
            if dep.split("[")[0].lower() == trigger.lower():
                trace_found = True
                break
        
        if trace_found:
            framework_additions.extend(extras)
    
    if framework_additions:
        from .utils import print_step
        print_step(f"Detected frameworks, adding extras: {', '.join(framework_additions)}")
        final_deps.update(framework_additions)

    # 6b. Deduplicate: If package[extra] is present, remove package
    # e.g. if "passlib[bcrypt]" is in list, remove "passlib"
    # Logic: Collect all base names of satisfied extras.
    deps_with_extras = [d for d in final_deps if "[" in d]
    bases_to_remove = set()
    for d in deps_with_extras:
        base = d.split("[")[0]
        bases_to_remove.add(base)
    
    # Remove dependencies that differ from the base only by not having the extra
    # AND are in the removal set.
    # Note: "passlib" matches base "passlib". "passlib[bcrypt]" does NOT match base "passlib".
    # We want to remove "passlib" if "passlib" in final_deps AND "passlib" in bases_to_remove.
    # 6b. Deduplicate and Merge Extras: 
    # If we have "pipecat-ai[aws]" and "pipecat-ai[google]", we want "pipecat-ai[aws,google]"
    
    merged_deps = {}
    
    for dep in final_deps:
        # Parse dep string
        if "[" in dep:
            base = dep.split("[")[0]
            extras_part = dep.split("[")[1].strip("]")
            extras = set(e.strip() for e in extras_part.split(","))
        else:
            base = dep
            extras = set()
            
        # Version pin handling? 
        # If versions differ, we might have issues. For now assume consistent versions or latest.
        # If "pkg==1.0" and "pkg[extra]", we keep version?
        # Let's strip version for key, but keep it for final reconstruction?
        # Actually simplest approach:
        # Key = base_name.
        # Value = { "extras": set(), "version": str|None }
        
        # Handling version:
        version = None
        if "==" in base:
            parts = base.split("==")
            base_name = parts[0]
            version = parts[1]
        else:
            base_name = base
            
        if base_name not in merged_deps:
            merged_deps[base_name] = {"extras": set(), "version": version}
        
        merged_deps[base_name]["extras"].update(extras)
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
            suffix = f"[{sorted_extras}]"
            
        dep_str = f"{pkg}{suffix}"
        if version:
            dep_str += f"=={version}"
            
        final_deps_list.append(dep_str)

    final_deps = set(final_deps_list)

    # 7. Version Pinning
    # Attempt to resolve versions for all final dependencies
    pinned_deps = []
    
    # Strategy: Use `uv pip compile` to resolve compatible versions if available.
    # This respects python version constraints and solves for conflicts.
    
    from .utils import check_command_exists

    
    resolved_map = {}
    uv_success = False
    
    
    if check_command_exists("uv") and False: # Force Disable UV for speed
        # USER REQUEST: Disable uv pip compile for speed.
        # USER REQUEST: Disable uv pip compile for speed.
        # It takes too long on large graphs.
        # We will just verify existence and use latest compatible if possible, or just latest.
        # For now, we skip the compile step.
        pass


    if not uv_success:
        # Fallback to PyPI JSON "latest"
        # Skipped for speed in Phase 2 optimization. 
        # We value "dead instant" inference over "latest version pinned" inference.
        pass
        # from .pypi import get_latest_version
        # with ThreadPoolExecutor(max_workers=50) as executor:
        #     future_to_dep = {executor.submit(get_latest_version, dep): dep for dep in final_deps}
        #     for future in as_completed(future_to_dep):
        #         dep = future_to_dep[future]
        #         try:
        #             version = future.result()
        #             if version:
        #                 resolved_map[dep.lower()] = f"{dep}=={version}"
        #         except Exception:
        #             pass

    # Apply resolved versions
    for dep in final_deps:
        # dep might be "passlib[bcrypt]"
        # resolved_map key might be "passlib"
        clean_name = dep.split("[")[0].lower()
        
        if clean_name in resolved_map:
            # Map has "passlib==1.7.4". We want "passlib[bcrypt]==1.7.4"
            # Extract version from resolved string
            resolved_str = resolved_map[clean_name]
            # Use original dep string + version
            version = resolved_str.split("==")[1]
            pinned_deps.append(f"{dep}=={version}")
        else:
            # If the dependency already has a version pin (from framework extras), keep it
            if "==" in dep:
                 pinned_deps.append(dep)
            else:
                 pinned_deps.append(dep)

    return sorted(list(set(pinned_deps)))
