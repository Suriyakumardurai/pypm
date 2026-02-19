import argparse
from pathlib import Path

from .scanner import scan_directory
from .parser import get_imports_from_file
from .resolver import resolve_dependencies
from .installer import install_packages
from .utils import print_success, print_error, print_warning, HAS_RICH



def is_dev_file(filepath, root_path):
    """
    Determines if a file is a development file (tests, docs, examples).
    """
    # Check path components
    try:
        rel_path = filepath.relative_to(root_path)
        parts = rel_path.parts
    except ValueError:
        return False  # Should not happen if start path is correct

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

def get_project_dependencies(root_path):
    """
    Core logic to scan, parse, and resolve dependencies.
    Returns (prod_dependencies, dev_dependencies).
    """
    from .heuristics import run_heuristics
    from .utils import console
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 1. Scan directory (Fast)
    if HAS_RICH:
        with console.status("[bold green]Scanning project files...[/bold green]", spinner="dots"):
            py_files = scan_directory(root_path)
    else:
        print("Scanning project files...")
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
    max_workers = min(32, len(py_files)) if len(py_files) > 0 else 1

    if HAS_RICH:
        status_ctx = console.status(
            "[bold green]Analyzing %d files...[/bold green]" % len(py_files),
            spinner="dots"
        )
    else:
        print("Analyzing %d files..." % len(py_files))
        status_ctx = None

    # Use context manager only if rich is available
    if status_ctx is not None:
        status_ctx.__enter__()

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(get_imports_from_file, f): f for f in py_files}

            for future in as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    imports_data = future.result()
                    runtime = imports_data.get("runtime", set()) | imports_data.get("dynamic", set())
                    typing_imports = imports_data.get("typing", set())

                    if is_dev_file(file, root_path):
                        dev_imports.update(runtime)
                        dev_imports.update(typing_imports)
                    else:
                        prod_imports.update(runtime)
                        dev_imports.update(typing_imports)
                except Exception:
                    # Silently ignore or log debug if needed
                    pass

        # Heuristics (Sequential but fast)
        implicit_deps = run_heuristics(root_path, prod_imports)
        if implicit_deps:
            prod_imports.update(implicit_deps)
    finally:
        if status_ctx is not None:
            status_ctx.__exit__(None, None, None)

    # 3. Resolve (Fast internal resolution)
    if HAS_RICH:
        with console.status("[bold green]Resolving dependencies...[/bold green]", spinner="dots"):
            resolved_prod = resolve_dependencies(prod_imports, str(root_path), local_modules)
            resolved_dev = resolve_dependencies(dev_imports, str(root_path), local_modules)
    else:
        print("Resolving dependencies...")
        resolved_prod = resolve_dependencies(prod_imports, str(root_path), local_modules)
        resolved_dev = resolve_dependencies(dev_imports, str(root_path), local_modules)

    # Deduplicate
    def get_pkg_name(dep):
        return dep.split("[")[0].split("==")[0].lower()

    prod_names = set(get_pkg_name(d) for d in resolved_prod)
    final_dev = []
    for d in resolved_dev:
        if get_pkg_name(d) not in prod_names:
            final_dev.append(d)

    return resolved_prod, final_dev

def generate_pyproject_toml(dependencies, dev_dependencies, path):
    """
    Generates a pyproject.toml file with the given dependencies.
    """
    toml_path = path / "pyproject.toml"

    # Basic template
    content = [
        "[project]",
        'name = "%s"' % path.name,
        'version = "0.1.0"',
        'description = ""',
        'readme = "README.md"',
        'requires-python = ">=3.8"',
        "dependencies = ["
    ]

    for dep in sorted(dependencies):
        content.append('    "%s",' % dep)
    content.append("]")

    content.append("")
    content.append("[dependency-groups.dev]")
    content.append("dependencies = [")
    for dep in sorted(dev_dependencies):
        content.append('    "%s",' % dep)
    content.append("]")

    # Write to file
    try:
        with open(str(toml_path), "w") as f:
            f.write("\n".join(content))
    except Exception as e:
        print_error("Failed to write pyproject.toml: %s" % str(e))

def command_infer(args):
    root_path = Path(args.path).resolve()
    if not root_path.exists():
        print_error("Error: Path '%s' does not exist." % str(root_path))
        return

    prod_deps, dev_deps = get_project_dependencies(root_path)

    # Display results
    if HAS_RICH:
        from rich.tree import Tree
        from .utils import console

        tree = Tree("[bold]Project: %s[/bold]" % root_path.name)

        if prod_deps:
            prod_branch = tree.add("[bold green]Production (%d)[/bold green]" % len(prod_deps))
            for dep in prod_deps:
                prod_branch.add("[green]%s[/green]" % dep)
        else:
            tree.add("[yellow]No production dependencies[/yellow]")

        if dev_deps:
            dev_branch = tree.add("[bold blue]Development (%d)[/bold blue]" % len(dev_deps))
            for dep in dev_deps:
                dev_branch.add("[blue]%s[/blue]" % dep)

        console.print(tree)
        console.print("")
    else:
        # Plain text fallback
        print("Project: %s" % root_path.name)
        print("")
        if prod_deps:
            print("Production (%d):" % len(prod_deps))
            for dep in prod_deps:
                print("  - %s" % dep)
        else:
            print("No production dependencies")
        print("")
        if dev_deps:
            print("Development (%d):" % len(dev_deps))
            for dep in dev_deps:
                print("  - %s" % dep)
        print("")

    if getattr(args, "dry_run", False):
        print("Dry run enabled. No files were modified.")
        return

    generate_pyproject_toml(prod_deps, dev_deps, root_path)
    print_success("Updated %s" % str(root_path / "pyproject.toml"))

def command_install(args):
    root_path = Path(args.path).resolve()
    if not root_path.exists():
        print_error("Error: Path '%s' does not exist." % str(root_path))
        return

    prod_deps, dev_deps = get_project_dependencies(root_path)

    if not prod_deps and not dev_deps:
        print("No dependencies to install.")
        return

    # Generate pyproject.toml first
    generate_pyproject_toml(prod_deps, dev_deps, root_path)
    print_success("Updated %s" % str(root_path / "pyproject.toml"))

    # Install packages
    all_deps = prod_deps + dev_deps

    print("")
    print("Installing %d packages..." % len(all_deps))

    if HAS_RICH:
        from .utils import console
        with console.status("[bold green]Installing packages...[/bold green]", spinner="dots"):
            success = install_packages(all_deps)
    else:
        success = install_packages(all_deps)

    if success:
        print_success("Installation complete!")
    else:
        print_error("Installation failed.")

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
        try:
            import importlib.metadata as _meta
            version = _meta.version("pypm-cli")
        except Exception:
            try:
                import importlib_metadata as _meta_backport  # type: ignore[import-untyped,import-not-found]
                version = _meta_backport.version("pypm-cli")
            except Exception:
                version = "0.0.5"

        print("pypm-cli %s" % version)
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
