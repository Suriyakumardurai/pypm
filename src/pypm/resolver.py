import sys
from typing import Set, List
import importlib.metadata
import os
from .utils import log
from .pypi import find_pypi_package

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
}

# Framework specific additions (if key is found, add value)
FRAMEWORK_EXTRAS = {
    "fastapi": ["uvicorn[standard]", "python-multipart", "email-validator"],
    "passlib": ["passlib[bcrypt]", "bcrypt==4.1.2"], # Pin bcrypt to 4.1.2 for passlib compatibility
    "sqlalchemy": ["greenlet"], # Async SQLAlchemy often needs greenlet explicitly
}

def is_stdlib(module_name: str) -> bool:
    """
    Checks if a module is in the standard library.
    """
    if module_name.startswith("_"): 
        return True 
    return module_name in STDLIB_MODULES

def is_local_module(module_name: str, project_root: str) -> bool:
    """
    Checks if a module is part of the local project by searching for it.
    """
    # 1. Simple Top-Level Check
    if os.path.exists(os.path.join(project_root, f"{module_name}.py")):
        return True
    if os.path.exists(os.path.join(project_root, module_name, "__init__.py")):
        return True
        
    # 2. Recursive Check (for flat layouts or src layouts)
    # If we are in root, and imports are like `import utils`, but utils is at `pypm/utils.py`
    # This implies the user is running from root but the code expects `pypm` to be in path?
    # Or relative imports were parsed as absolute?
    # AST parser: `from . import utils` -> module="utils" (level=1)? No.
    # `from .utils import log` -> module="utils"?
    
    # Wait, my parser logic:
    # `elif isinstance(node, ast.ImportFrom): if node.module: imports.add(node.module.split('.')[0])`
    # If `from .utils import log` -> node.module is likely None or "utils" depending on python version?
    # Actually, if level > 0, module might be None or the "utils" part.
    # But `node.module` IS `utils` for `from .utils import ...`? 
    # Let's assume standard absolute imports for now.
    
    # Heuristic: Walk the directory to see if `module_name.py` exists ANYWHERE in the project.
    # This is risky (might match `tests/utils.py` and think `import utils` is local).
    # But for a project manager, if `utils.py` exists in the project, it's safer to assume it's local
    # than to install `utils` from PyPI (which is a common mistake).
    
    for root, dirs, files in os.walk(project_root):
        # Skip venvs
        if "site-packages" in root or ".venv" in root or "venv" in root:
            continue
            
        if f"{module_name}.py" in files:
            return True
        if module_name in dirs:
            if os.path.exists(os.path.join(root, module_name, "__init__.py")):
                return True
                
    return False

# Packages that exist on PyPI but are almost always local modules in user projects
SUSPICIOUS_PACKAGES = {
    "core", "modules", "crm", "ledgers", "config", "utils", "common", "tests", "settings", "db", "database"
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

def resolve_dependencies(imports: Set[str], project_root: str) -> List[str]:
    """
    Resolves imports to distribution packages using Online PyPI verification.
    """
    dependencies = []
    
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Prepare list of candidates to check
    candidates_to_check = []
    
    for module in imports:
        # 1. Filter Standard Library
        if is_stdlib(module):
            log(f"Ignored stdlib module: {module}", level="DEBUG")
            continue
            
        # 2. Filter Local Modules
        if is_local_module(module, project_root):
            log(f"Ignored local module: {module}", level="DEBUG")
            continue
            
        # 3. Filter Suspicious/Generic Names
        if module in SUSPICIOUS_PACKAGES:
             log(f"Ignored suspicious/generic module name: {module} (likely local)", level="DEBUG")
             continue

        # 4. Fast Path: Common Mappings
        if module in COMMON_MAPPINGS:
            dependencies.append(COMMON_MAPPINGS[module])
            continue
            
        # 5. Queue for Online Check
        candidates_to_check.append(module)
    
    # 5. Online Verification (Parallelized for speed)
    if candidates_to_check:
        from .utils import print_step
        print_step(f"Verifying {len(candidates_to_check)} packages on PyPI...")
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_module = {executor.submit(find_pypi_package, m): m for m in candidates_to_check}
            
            for future in as_completed(future_to_module):
                module = future_to_module[future]
                try:
                    pypi_name = future.result()
                    if pypi_name:
                        log(f"Verified '{module}' -> '{pypi_name}' on PyPI", level="DEBUG")
                        dependencies.append(pypi_name)
                    else:
                        log(f"Warning: Could not find package for import '{module}' on PyPI.", level="DEBUG")
                        # Do NOT add it if not found (Zero Error policy)
                except Exception as e:
                    log(f"Error verifying {module}: {e}", level="ERROR")
    
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
    final_deps = {d for d in final_deps if d not in bases_to_remove} | set(deps_with_extras)
    
    # 7. Version Pinning
    # Attempt to resolve versions for all final dependencies
    pinned_deps = []
    
    # Strategy: Use `uv pip compile` to resolve compatible versions if available.
    # This respects python version constraints and solves for conflicts.
    
    from .utils import check_command_exists
    import subprocess
    
    resolved_map = {}
    uv_success = False
    
    if check_command_exists("uv"):
        from .utils import print_step
        print_step("Resolving versions with 'uv' for compatibility...")
        try:
            # Create a requirements input string
            # We use local python version by default by not specifying --python-version
            # But we should use --python-platform maybe? No, defaults are usually fine for "standard".
            input_reqs = "\n".join(final_deps)
            
            # Run uv pip compile
            # We use --universal if we want broader compatibility, but user wants "standard" for THIS env mostly.
            # Let's use default behavior which resolves for current environment.
            proc = subprocess.run(
                ["uv", "pip", "compile", "-", "--quiet", "--no-header", "--no-annotate", "--no-emit-index-url"],
                input=input_reqs.encode("utf-8"),
                capture_output=True,
                check=False
            )
            
            if proc.returncode == 0:
                output = proc.stdout.decode("utf-8")
                # Parse output: "package==version"
                for line in output.splitlines():
                    line = line.strip()
                    if "==" in line and not line.startswith("#"):
                        parts = line.split("==")
                        pkg = parts[0].strip()
                        ver = parts[1].strip()
                        # Clean extras from pkg name for matching if needed, 
                        # but pip compile output usually has clean names?
                        # Actually verify against our deps.
                        resolved_map[pkg.lower()] = f"{pkg}=={ver}"
                        # Also handle extras syntax in output if present (rare in list, usually just name==ver)
                uv_success = True
            else:
                log(f"uv resolution failed: {proc.stderr.decode('utf-8')}", level="DEBUG")
        except Exception as e:
            log(f"Error running uv: {e}", level="DEBUG")

    if not uv_success:
        # Fallback to PyPI JSON "latest"
        log("Falling back to PyPI latest version check...", level="INFO")
        from .pypi import get_latest_version
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_dep = {executor.submit(get_latest_version, dep): dep for dep in final_deps}
            for future in as_completed(future_to_dep):
                dep = future_to_dep[future]
                try:
                    version = future.result()
                    if version:
                        # Clean dep name to avoid extras mess in map?
                        # Just use dep as key.
                        resolved_map[dep.lower()] = f"{dep}=={version}"
                except Exception:
                    pass

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
