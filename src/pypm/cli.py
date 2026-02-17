import argparse
from pathlib import Path
from typing import List



from .scanner import scan_directory
from .parser import get_imports_from_file
from .resolver import resolve_dependencies
from .installer import install_packages
from .utils import log, print_step, print_success, print_error, print_warning, BOLD, GREEN, RESET

def get_project_dependencies(root_path: Path) -> List[str]:
    """
    Core logic to scan, parse, and resolve dependencies.
    """
    print_step("Scanning for .py files...")
    py_files = scan_directory(root_path)
    if not py_files:
        print_warning("No .py files found.")
        return []
        
    all_imports = set()
    for file in py_files:
        imports = get_imports_from_file(file)
        all_imports.update(imports)
        
    log(f"Found imports: {', '.join(sorted(all_imports))}", level="DEBUG")
    
    dependencies = resolve_dependencies(all_imports, str(root_path))
    return dependencies

def generate_pyproject_toml(dependencies: List[str], path: Path):
    """
    Generates or updates pyproject.toml with dependencies (PEP 621).
    """
    pyproject_path = path / "pyproject.toml"
    
    current_deps = set()
    content_lines = []
    
    if pyproject_path.exists():
        log("Found existing pyproject.toml, attempting to merge...", level="DEBUG")
        try:
            with open(pyproject_path, "r", encoding="utf-8") as f:
                content_lines = f.readlines()
        except Exception as e:
            log(f"Failed to read pyproject.toml: {e}", level="ERROR")
            return
            
        # Very basic parsing to find existing dependencies in `dependencies = [...]`
        # This assumes a specific format for MVP simplicity if tomlib is missing.
        # We look for lines containing strings inside the dependencies list.
        in_deps = False
        for line in content_lines:
            stripped = line.strip()
            if stripped.startswith("dependencies = ["):
                in_deps = True
                # Check for inline list like dependencies = ["a", "b"]
                if "]" in stripped: 
                     # Parse inline (rudimentary)
                     parts = stripped.split("[")[1].split("]")[0].split(",")
                     for p in parts:
                         d = p.strip().strip('"').strip("'")
                         if d:
                            current_deps.add(d)
                     in_deps = False # Ended on same line
                continue
            
            if in_deps:
                if stripped.startswith("]"):
                    in_deps = False
                    continue
                # Line should be a string literal like "pkg",
                clean_dep = stripped.strip(",").strip('"').strip("'")
                if clean_dep:
                    current_deps.add(clean_dep)
    else:
        log("Generating new pyproject.toml...", level="DEBUG")
        content_lines = [
            "[project]\n",
            "name = \"auto-generated\"\n",
            "version = \"0.1.0\"\n",
            "dependencies = [\n",
            "]\n"
        ]

    # Calculate new deps - NO, we essentially overwrite with *dependencies* (which are the source of truth)
    # But checking for diff is good for logging.
    # Actually, we just want to enforce the inferred state.
    
    new_deps_set = set(dependencies)
    
    # We need to inject new deps into the `dependencies = [...]` list.
    # Logic: Find the line with `dependencies = [` (start) and `]` (end).
    # If not found, append valid block.
    
    new_content_lines = []

    
    # Check if we have a dependencies block
    has_deps_block = any(line.strip().startswith("dependencies = [") for line in content_lines)
    
    if has_deps_block:
        in_old_deps_block = False
        for line in content_lines:
            stripped = line.strip()
            
            # Start of block
            if stripped.startswith("dependencies = ["):
                new_content_lines.append("dependencies = [\n")
                
                for dep in sorted(new_deps_set):
                    new_content_lines.append(f'    "{dep}",\n')
                new_content_lines.append("]\n")

                
                # Check formatting of old block
                if "]" in stripped:
                    # Inline block ended on same line.
                    continue
                else:
                    # Multi-line block starts here. Skip lines until closing bracket.
                    in_old_deps_block = True
                continue
                
            if in_old_deps_block:
                if stripped.startswith("]"):
                    in_old_deps_block = False
                continue
                
            new_content_lines.append(line)
    else:
        # Append to end if no block found
        new_content_lines = content_lines
        if new_content_lines and not new_content_lines[-1].endswith("\n"):
             new_content_lines.append("\n")
             
        new_content_lines.append("dependencies = [\n")
        for dep in sorted(new_deps_set):
            new_content_lines.append(f'    "{dep}",\n')
        new_content_lines.append("]\n")


    try:
        with open(pyproject_path, "w", encoding="utf-8") as f:
            f.writelines(new_content_lines)
        log(f"Updated {pyproject_path} with {len(new_deps_set)} dependencies.", level="DEBUG")
    except Exception as e:
        print_error(f"Failed to write pyproject.toml: {e}")

def command_infer(args):
    root_path = Path(args.path).resolve()
    if not root_path.exists():
        log(f"Error: Path '{root_path}' does not exist.", level="ERROR")
        return
        
    dependencies = get_project_dependencies(root_path)
    
    # We proceed even if empty, to ensure pyproject.toml is cleared/updated.
    if dependencies:
        print_success(f"Found {len(dependencies)} external dependencies:")
        for dep in dependencies:
            print(f"  {GREEN}+ {dep}{RESET}")
    else:
        print_warning("No external dependencies found.")

    if getattr(args, "dry_run", False):
        print_step("Dry run enabled. No files were modified.")
        return

    generate_pyproject_toml(dependencies, root_path)
    print_success(f"Updated {BOLD}{root_path / 'pyproject.toml'}{RESET}")

def command_install(args):
    root_path = Path(args.path).resolve()
    if not root_path.exists():
        log(f"Error: Path '{root_path}' does not exist.", level="ERROR")
        return
        
    log(f"Inferring dependencies in {root_path}...", level="INFO")
    dependencies = get_project_dependencies(root_path)
    
    if not dependencies:
        log("No dependencies to install.", level="INFO")
        return
        
    # We need to install in the CONTEXT of that project?
    # uv run? or just install packages?
    # install_packages runs `uv pip install ...`. 
    # If we are in global mode, it installs to current environment.
    # If the user wants to install TO that project's venv, they should activate it first?
    # Or we just install the packages.
    # MVP: Install packages to the current environment / active venv.
    install_packages(dependencies)

def main():
    parser = argparse.ArgumentParser(description="pypm - Python Project Manager")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", required=False)
    
    # Infer command
    parser_infer = subparsers.add_parser("infer", help="Infer dependencies and generate pyproject.toml")
    parser_infer.add_argument("path", nargs="?", default=".", help="Path to project directory (default: current)")
    parser_infer.add_argument("--dry-run", action="store_true", help="Print dependencies without modifying files")
    parser_infer.set_defaults(func=command_infer)
    
    # Install command
    parser_install = subparsers.add_parser("install", help="Infer and install dependencies")
    parser_install.add_argument("path", nargs="?", default=".", help="Path to project directory (default: current)")
    parser_install.set_defaults(func=command_install)
    
    # Version command
    parser.add_argument("--version", action="store_true", help="Show version and exit")

    args = parser.parse_args()
    
    if args.version:
        import importlib.metadata
        try:
            version = importlib.metadata.version("pypm-cli")
        except importlib.metadata.PackageNotFoundError:
            version = "0.0.1"
            
        print(f"pypm-cli {version}")
        return

    if args.verbose:
        import logging
        from .utils import logger
        logger.setLevel(logging.DEBUG)
        
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
