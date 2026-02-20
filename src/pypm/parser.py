import ast
import json
import os
from pathlib import Path  # noqa: F401
from typing import Dict, Optional, Set  # noqa: F401

from .utils import log

# Security: Maximum file size to parse (10MB)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# ---- Import Cache (mtime + size based) ----
# Skips re-parsing files that haven't changed since last run.
# Key: (filepath_str, mtime_ns, size) -> parsed imports dict
_IMPORT_CACHE = {}  # type: Dict[str, dict]


def _get_file_key(filepath):
    # type: (Path) -> Optional[str]
    """Returns a cache key based on path + mtime + size. None if stat fails."""
    try:
        st = os.stat(str(filepath))
        return "%s|%d|%d" % (str(filepath), st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def _has_imports(content):
    # type: (str) -> bool
    """
    Ultra-fast pre-filter: checks if file content contains import-related keywords.
    If no imports/requires patterns exist, skip expensive AST parsing entirely.
    """
    return "import " in content or "import_module" in content or "__import__" in content


class ImportVisitor(ast.NodeVisitor):
    __slots__ = ("imports", "typing_imports", "dynamic_imports",
                 "in_type_checking", "in_try_block", "in_except_block")

    def __init__(self):
        self.imports = set()
        self.typing_imports = set()
        self.dynamic_imports = set()
        self.in_type_checking = False
        self.in_try_block = False
        self.in_except_block = False

    def visit_Import(self, node):
        for alias in node.names:
            base_module = alias.name.split('.')[0]

            if self.in_type_checking:
                self.typing_imports.add(base_module)
                self.typing_imports.add(alias.name)
            else:
                self.imports.add(base_module)
                self.imports.add(alias.name)

        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.level > 0:
            return

        target_set = self.typing_imports if self.in_type_checking else self.imports

        if node.module:
            base_module = node.module.split('.')[0]
            target_set.add(base_module)
            target_set.add(node.module)

        self.generic_visit(node)

    def visit_If(self, node):
        is_type_checking = False
        try:
           if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
               is_type_checking = True
           elif isinstance(node.test, ast.Attribute) and node.test.attr == "TYPE_CHECKING":
               is_type_checking = True
        except Exception:
            pass

        if is_type_checking:
            prev_state = self.in_type_checking
            self.in_type_checking = True
            for child in node.body:
                self.visit(child)
            self.in_type_checking = prev_state

            for child in node.orelse:
                self.visit(child)
        else:
            self.generic_visit(node)

    def visit_Try(self, node):
        prev_try = self.in_try_block
        prev_except = self.in_except_block

        self.in_try_block = True
        self.in_except_block = False
        for child in node.body:
            self.visit(child)
        self.in_try_block = prev_try

        self.in_except_block = True
        self.in_try_block = False
        for handler in node.handlers:
            is_import_error_handler = False
            if handler.type is None:
                is_import_error_handler = True
            elif isinstance(handler.type, ast.Name):
                if handler.type.id in ("ImportError", "ModuleNotFoundError", "Exception"):
                    is_import_error_handler = True
            elif isinstance(handler.type, ast.Tuple):
                for elt in handler.type.elts:
                    if isinstance(elt, ast.Name) and elt.id in ("ImportError", "ModuleNotFoundError"):
                        is_import_error_handler = True
                        break

            if is_import_error_handler:
                for child in handler.body:
                    self.visit(child)
            else:
                for child in handler.body:
                    self.visit(child)

        self.in_except_block = prev_except

        for child in node.orelse:
            self.visit(child)
        if hasattr(node, 'finalbody'):
            for child in node.finalbody:
                self.visit(child)

    def visit_Call(self, node):
        try:
            module_name = None
            if isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                if node.args and isinstance(node.args[0], (ast.Constant, ast.Str)):
                     val = node.args[0].value if isinstance(node.args[0], ast.Constant) else node.args[0].s
                     module_name = val
            elif isinstance(node.func, ast.Name) and node.func.id == "__import__":
                if node.args and isinstance(node.args[0], (ast.Constant, ast.Str)):
                     val = node.args[0].value if isinstance(node.args[0], ast.Constant) else node.args[0].s
                     module_name = val

            if module_name and isinstance(module_name, str):
                base = module_name.split('.')[0]
                self.dynamic_imports.add(base)
        except Exception:
            pass
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            val = node.value
            target_set = self.typing_imports if self.in_type_checking else self.imports

            if "mysql" in val and ("://" in val or "+aiomysql" in val):
                if "aiomysql" in val:
                    target_set.add("aiomysql")
                elif "pymysql" in val:
                    target_set.add("pymysql")
                else:
                    target_set.add("mysqlclient")

            elif "postgres" in val and ("://" in val or "+asyncpg" in val or "+psycopg" in val):
                if "asyncpg" in val:
                    target_set.add("asyncpg")
                elif "psycopg" in val:
                    target_set.add("psycopg2-binary")
                else:
                    target_set.add("psycopg2-binary")

            elif "mssql" in val and ("://" in val or "+pyodbc" in val):
                target_set.add("pyodbc")

            elif "redis://" in val:
                target_set.add("redis")
            elif "sqlite://" in val:
                pass
            elif "mongodb://" in val:
                target_set.add("pymongo")
        self.generic_visit(node)

    def visit_Str(self, node):
        self.visit_Constant(node)


# Empty result singleton to avoid re-creating dict+sets for no-import files
_EMPTY_RESULT = {"runtime": frozenset(), "typing": frozenset(), "dynamic": frozenset()}  # type: Dict[str, frozenset]


def _read_file_safe(filepath):
    # type: (Path) -> Optional[str]
    """Reads a file with encoding fallback and size limit."""
    try:
        file_size = filepath.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            return None
        if file_size == 0:
            return ""
    except OSError:
        return None

    for encoding in ("utf-8", "latin-1"):
        try:
            with open(str(filepath), "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception:
            return None

    return None


def get_imports_from_notebook(filepath):
    # type: (Path) -> dict
    """Parses a Jupyter Notebook (.ipynb) and returns imports."""
    result = {
        "runtime": set(),
        "typing": set(),
        "dynamic": set()
    }  # type: Dict[str, Set[str]]
    try:
        try:
            file_size = filepath.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                return result
        except OSError:
            return result

        with open(str(filepath), "r", encoding="utf-8") as f:
            notebook = json.load(f)

        code_lines = []
        for cell in notebook.get("cells", []):
            if cell.get("cell_type") == "code":
                source = cell.get("source", [])
                if isinstance(source, str):
                    code_lines.append(source)
                elif isinstance(source, list):
                    code_lines.extend(source)
                code_lines.append("\n")

        full_code = "".join(code_lines)

        if not _has_imports(full_code):
            return result

        tree = ast.parse(full_code, filename=str(filepath))
        visitor = ImportVisitor()
        visitor.visit(tree)

        result["runtime"] = visitor.imports
        result["typing"] = visitor.typing_imports
        result["dynamic"] = visitor.dynamic_imports

    except Exception as e:
        log("Error parsing notebook %s: %s" % (str(filepath), str(e)), level="ERROR")

    return result

def get_imports_from_file(filepath):
    # type: (Path) -> dict
    """
    Parses a python file or notebook and returns imports.
    Uses mtime-based caching to skip unchanged files.
    Uses pre-filter to skip files without import keywords.
    """
    if str(filepath).endswith(".ipynb"):
        return get_imports_from_notebook(filepath)

    # Check import cache (mtime + size based)
    cache_key = _get_file_key(filepath)
    if cache_key is not None and cache_key in _IMPORT_CACHE:
        return _IMPORT_CACHE[cache_key]

    result = {
        "runtime": set(),
        "typing": set(),
        "dynamic": set()
    }  # type: Dict[str, Set[str]]

    content = _read_file_safe(filepath)
    if content is None:
        return result

    # Fast pre-filter: skip AST parse if no import-related keywords
    if not _has_imports(content):
        if cache_key is not None:
            _IMPORT_CACHE[cache_key] = _EMPTY_RESULT
        return _EMPTY_RESULT

    try:
        tree = ast.parse(content, filename=str(filepath))

        visitor = ImportVisitor()
        visitor.visit(tree)

        result["runtime"] = visitor.imports
        result["typing"] = visitor.typing_imports
        result["dynamic"] = visitor.dynamic_imports

        # Cache the result
        if cache_key is not None:
            _IMPORT_CACHE[cache_key] = result

    except SyntaxError as e:
        log("Syntax error in %s: %s" % (str(filepath), str(e)), level="ERROR")
    except Exception as e:
        log("Error parsing %s: %s" % (str(filepath), str(e)), level="ERROR")

    return result
