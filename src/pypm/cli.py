import argparse
from pathlib import Path
from typing import List, Tuple



from .scanner import scan_directory
from .parser import get_imports_from_file
from .resolver import resolve_dependencies
from .installer import install_packages
from .utils import print_success, print_error, print_warning



def is_dev_file(filepath: Path, root_path: Path) -> bool:
    """
    Determines if a file is a development file (tests, docs, examples).
    """
    # Check path components
    try:
        rel_path = filepath.relative_to(root_path)
        parts = rel_path.parts
    except ValueError:
        return False # Should not happen if start path is correct

    for part in parts:
        lower_part = part.lower()
        if lower_part in {"tests", "test", "docs", "examples", "scripts"}:
            return True
            
    # Check filename patterns
    name = filepath.name.lower()
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if name == "conftest.py":
        return True
        
    return False

def get_project_dependencies(root_path: Path) -> Tuple[List[str], List[str]]:
    """
    Core logic to scan, parse, and resolve dependencies.
    Returns (prod_dependencies, dev_dependencies).
    """
    from .heuristics import run_heuristics
    from .utils import console
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 1. Scan directory (Fast)
    with console.status("[bold green]Scanning project files...[/bold green]", spinner="dots"):
        py_files = scan_directory(root_path)
    
    
    if not py_files:
        print_warning("No .py files found.")
        return [], []
        
    prod_imports = set()
    dev_imports = set()
    local_modules = set()

    # Pre-compute local modules set (Performance Optimization)
    # This is fast enough to keep sequential
    for p in py_files:
        local_modules.add(p.stem)
        if p.name == "__init__.py":
            local_modules.add(p.parent.name)

    # 2. Parse files in parallel (Aggressive Multithreading)
    # Using a large number of workers for IO/CPU mix
    max_workers = min(32, len(py_files)) if len(py_files) > 0 else 1
    
    with console.status(f"[bold green]Analyzing {len(py_files)} files...[/bold green]", spinner="dots"):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(get_imports_from_file, f): f for f in py_files}
            
            for future in as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    imports_data = future.result()
                    runtime = imports_data.get("runtime", set()) | imports_data.get("dynamic", set())
                    typing = imports_data.get("typing", set())
                    
                    if is_dev_file(file, root_path):
                        dev_imports.update(runtime)
                        dev_imports.update(typing)
                    else:
                        prod_imports.update(runtime)
                        dev_imports.update(typing)
                except Exception:
                    # Silently ignore or log debug if needed
                    pass

        # Heuristics (Sequential but fast)
        implicit_deps = run_heuristics(root_path, prod_imports)
        if implicit_deps:
            # Only log if verbose or just debug
            # console.log(f"[dim]Heuristics found: {', '.join(sorted(implicit_deps))}[/dim]")
            prod_imports.update(implicit_deps)

    # 3. Resolve (Fast internal resolution)
    # We pass local_modules to avoid unnecessary checks
    with console.status("[bold green]Resolving dependencies...[/bold green]", spinner="dots"):
        resolved_prod = resolve_dependencies(prod_imports, str(root_path), local_modules)
        resolved_dev = resolve_dependencies(dev_imports, str(root_path), local_modules)
    
    # Deduplicate
    def get_pkg_name(dep):
        return dep.split("[")[0].split("==")[0].lower()
        
    prod_names = {get_pkg_name(d) for d in resolved_prod}
    final_dev = []
    for d in resolved_dev:
        if get_pkg_name(d) not in prod_names:
            final_dev.append(d)
            
    return resolved_prod, final_dev

def generate_pyproject_toml(dependencies: List[str], dev_dependencies: List[str], path: Path):
    """
    Generates a pyproject.toml file with the given dependencies.
    """
    toml_path = path / "pyproject.toml"
    
    # Basic template
    content = [
        "[project]",
        f"name = \"{path.name}\"",
        "version = \"0.1.0\"",
        "description = \"\"",
        "readme = \"README.md\"",
        "requires-python = \">=3.8\"",
        "dependencies = ["
    ]
    
    for dep in sorted(dependencies):
        content.append(f"    \"{dep}\",")
    content.append("]")
    
    content.append("")
    content.append("[dependency-groups.dev]")
    content.append("dependencies = [")
    for dep in sorted(dev_dependencies):
        content.append(f"    \"{dep}\",")
    content.append("]")
    
    # Write to file
    try:
        with open(toml_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content))
    except Exception as e:
        print_error(f"Failed to write pyproject.toml: {e}") 
    
    # Wait, I cannot skip the implementation of generate_pyproject_toml if I am replacing the whole file or large chunks.
    # The tool requires StartLine/EndLine.
    # I will stick to editing get_project_dependencies and command_infer/install.

def command_infer(args):
    from rich.tree import Tree
    from .utils import console
    
    root_path = Path(args.path).resolve()
    if not root_path.exists():
        console.print(f"[error]Error: Path '{root_path}' does not exist.[/error]")
        return
        
    prod_deps, dev_deps = get_project_dependencies(root_path)
    
    # Display Tree
    tree = Tree(f"[bold]Project: {root_path.name}[/bold]")
    
    if prod_deps:
        prod_branch = tree.add(f"[bold green]Production ({len(prod_deps)})[/bold green]")
        for dep in prod_deps:
            prod_branch.add(f"[green]{dep}[/green]")
    else:
        tree.add("[yellow]No production dependencies[/yellow]")

    if dev_deps:
        dev_branch = tree.add(f"[bold blue]Development ({len(dev_deps)})[/bold blue]")
        for dep in dev_deps:
            dev_branch.add(f"[blue]{dep}[/blue]")
            
    console.print(tree)
    console.print("")

    if getattr(args, "dry_run", False):
        console.print("[dim]Dry run enabled. No files were modified.[/dim]")
        return

    # Call original gen (I need to import it or ensure it's in scope if I didn't verify lines properly)
    # It is defined above in the file.
    generate_pyproject_toml(prod_deps, dev_deps, root_path)
    print_success(f"Updated [bold]{root_path / 'pyproject.toml'}[/bold]")

def command_install(args):
    from .utils import console

    root_path = Path(args.path).resolve()
    if not root_path.exists():
        console.print(f"[error]Error: Path '{root_path}' does not exist.[/error]")
        return
        
    prod_deps, dev_deps = get_project_dependencies(root_path)
    
    if not prod_deps and not dev_deps:
        console.print("[info]No dependencies to install.[/info]")
        return
        
    # Generate pyproject.toml first
    generate_pyproject_toml(prod_deps, dev_deps, root_path)
    console.print(f"[success]Updated [bold]{root_path / 'pyproject.toml'}[/bold][/success]")
    
    # Install packages
    all_deps = prod_deps + dev_deps
    
    console.print("")
    console.print(f"[bold]Installing {len(all_deps)} packages...[/bold]")
    
    with console.status("[bold green]Installing packages via uv...[/bold green]", spinner="dots"):
        success = install_packages(all_deps)
        
    if success:
        console.print("[success]✔ Installation complete![/success]")
    else:
        console.print("[error]✖ Installation failed.[/error]")

def main():
    parser = argparse.ArgumentParser(description="pypm - Python Package Manager")
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
            version = "0.0.4"
            
        print(f"pypm-cli {version}")
        return

    if args.verbose:
        from . import utils
        utils.VERBOSE = True
        
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
