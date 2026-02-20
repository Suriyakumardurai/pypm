import argparse
import time
from pathlib import Path

from .installer import install_packages
from .parser import get_imports_from_file
from .resolver import resolve_dependencies
from .scanner import iter_scan_directory as _iter_scan
from .scanner import scan_directory  # noqa: F401
from .utils import HAS_RICH, get_optimal_workers, print_error, print_success, print_warning


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
    Uses overlapping pipeline: scan → parse happen concurrently.
    """
    import queue
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from .heuristics import run_heuristics
    from .utils import console

    prod_imports = set()
    dev_imports = set()
    local_modules = set()

    # Pre-warm HTTP session immediately (runs in parallel with all scanning/parsing)
    # SSL/TLS handshake costs 200-500ms; starting it now means zero latency at resolution time
    def _prewarm_session():
        # type: () -> None
        try:
            from .pypi import _get_session
            _get_session()
        except Exception:
            pass

    prewarm = threading.Thread(target=_prewarm_session, daemon=True)
    prewarm.start()

    # Phase 1+2: OVERLAPPING scan + parse pipeline
    # Producer thread scans directories, consumer threads parse files immediately
    file_queue = queue.Queue()  # type: queue.Queue
    scan_done = threading.Event()


    if HAS_RICH:
        status_ctx = console.status(
            "[bold green]Scanning & analyzing project...[/bold green]",
            spinner="dots"
        )
    else:
        print("Scanning & analyzing project...")
        status_ctx = None

    if status_ctx is not None:
        status_ctx.__enter__()

    try:
        # Producer: scan directory in background thread
        def _scan_producer():
            # type: () -> None
            for f in _iter_scan(root_path):
                file_queue.put(f)
            scan_done.set()

        scan_thread = threading.Thread(target=_scan_producer, daemon=True)
        scan_thread.start()

        # Consumer: parse files as they arrive
        max_workers = get_optimal_workers(64, io_bound=True)  # Estimate high
        all_files = []  # type: list

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}  # type: dict
            while True:
                # Drain queue in batches
                batch = []  # type: list
                try:
                    while True:
                        f = file_queue.get_nowait()
                        batch.append(f)
                except queue.Empty:
                    pass

                for f in batch:
                    all_files.append(f)
                    futures[executor.submit(get_imports_from_file, f)] = f

                # Check if scan is done and queue is empty
                if scan_done.is_set() and file_queue.empty() and not batch:
                    break

                # Small sleep to avoid busy-waiting
                scan_done.wait(timeout=0.005)

            # Wait for remaining futures
            for future in as_completed(futures):
                file = futures[future]
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
                    pass

        scan_thread.join(timeout=2)

        if not all_files:
            print_warning("No .py files found.")
            return [], []

        # Pre-compute local modules from discovered files
        for p in all_files:
            local_modules.add(p.stem)
            if p.name == "__init__.py":
                local_modules.add(p.parent.name)

        # Heuristics (fast, sequential)
        implicit_deps = run_heuristics(root_path, prod_imports)
        if implicit_deps:
            prod_imports.update(implicit_deps)
    finally:
        if status_ctx is not None:
            status_ctx.__exit__(None, None, None)
    # 3. Resolve (Parallel prod + dev resolution)
    if HAS_RICH:
        status_resolve = console.status("[bold green]Resolving dependencies...[/bold green]", spinner="dots")
        status_resolve.__enter__()
    else:
        print("Resolving dependencies...")
        status_resolve = None

    try:
        with ThreadPoolExecutor(max_workers=2) as resolve_executor:
            future_prod = resolve_executor.submit(
                resolve_dependencies, prod_imports, str(root_path), local_modules
            )
            future_dev = resolve_executor.submit(
                resolve_dependencies, dev_imports, str(root_path), local_modules
            )
            resolved_prod = future_prod.result()
            resolved_dev = future_dev.result()
    finally:
        if status_resolve is not None:
            status_resolve.__exit__(None, None, None)

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

    start_time = time.time() if getattr(args, "bench", False) else None
    prod_deps, dev_deps = get_project_dependencies(root_path)
    if start_time:
        print("\n[BENCH] Core analysis time: %.3fs" % (time.time() - start_time))


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

    if start_time:
        print("[BENCH] Total execution time: %.3fs" % (time.time() - start_time))

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

    start_time = time.time() if getattr(args, "bench", False) else None
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

    if start_time:
        print("\n[BENCH] Execution time: %.3fs" % (time.time() - start_time))

def main():
    parser = argparse.ArgumentParser(description="pypm - Python Package Manager")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    subparsers = parser.add_subparsers(dest="command")

    # Infer command
    parser_infer = subparsers.add_parser("infer", help="Infer dependencies and generate pyproject.toml")
    parser_infer.add_argument("path", nargs="?", default=".", help="Path to project directory (default: current)")
    parser_infer.add_argument("--dry-run", action="store_true", help="Print dependencies without modifying files")
    parser_infer.add_argument("--bench", action="store_true", help="Display execution time")
    parser_infer.set_defaults(func=command_infer)

    # Install command
    parser_install = subparsers.add_parser("install", help="Infer and install dependencies")
    parser_install.add_argument("path", nargs="?", default=".", help="Path to project directory (default: current)")
    parser_install.add_argument("--bench", action="store_true", help="Display execution time")
    parser_install.set_defaults(func=command_install)

    # Version command
    parser.add_argument("--version", action="store_true", help="Show version and exit")

    args = parser.parse_args()

    if args.version:
        try:
            import importlib.metadata as _meta  # novm
            version = _meta.version("pypm-cli")
        except Exception:
            try:
                import importlib_metadata as _meta_backport  # type: ignore[import-untyped,import-not-found]
                version = _meta_backport.version("pypm-cli")
            except Exception:
                version = "0.0.6"

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
