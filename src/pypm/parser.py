import ast
from pathlib import Path  # noqa: F401
import json
from typing import Dict, Set, Optional  # noqa: F401
from .utils import log

# Security: Maximum file size to parse (10MB)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()
        self.typing_imports = set()
        self.dynamic_imports = set()
        self.in_type_checking = False
        self.in_try_block = False
        self.in_except_block = False

    def visit_Import(self, node):
        for alias in node.names:
            # Add base module
            base_module = alias.name.split('.')[0]

            if self.in_type_checking:
                self.typing_imports.add(base_module)
                self.typing_imports.add(alias.name)
            else:
                self.imports.add(base_module)
                self.imports.add(alias.name)

        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        # Ignore relative imports (level > 0)
        if node.level > 0:
            return

        target_set = self.typing_imports if self.in_type_checking else self.imports

        if node.module:
            base_module = node.module.split('.')[0]
            target_set.add(base_module)
            target_set.add(node.module)

        self.generic_visit(node)

    def visit_If(self, node):
        # Detect "if TYPE_CHECKING:" blocks
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
        """
        Handle try/except import patterns:
          try:
              import ujson as json    # Primary (add as dependency)
          except ImportError:
              import json             # Fallback (skip if stdlib)
        """
        # Save state
        prev_try = self.in_try_block
        prev_except = self.in_except_block

        # Visit try body normally — these are the primary imports we want
        self.in_try_block = True
        self.in_except_block = False
        for child in node.body:
            self.visit(child)
        self.in_try_block = prev_try

        # Visit except handlers — imports here are fallbacks
        # We still collect them, but the resolver will filter stdlibs anyway
        self.in_except_block = True
        self.in_try_block = False
        for handler in node.handlers:
            # Only suppress if this is an ImportError/ModuleNotFoundError handler
            is_import_error_handler = False
            if handler.type is None:
                # Bare except: — treat as import error handler to be safe
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
                # For except ImportError blocks, we still visit but the imports
                # collected here are fallbacks. The resolver's stdlib filter
                # will naturally remove stdlib fallbacks like `import json`.
                for child in handler.body:
                    self.visit(child)
            else:
                for child in handler.body:
                    self.visit(child)

        self.in_except_block = prev_except

        # Visit else and finally blocks normally
        for child in node.orelse:
            self.visit(child)
        if hasattr(node, 'finalbody'):
            for child in node.finalbody:
                self.visit(child)

    def visit_Call(self, node):
        # Detect dynamic imports
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
        # Scan string literals for database connection strings
        if isinstance(node.value, str):
            val = node.value
            target_set = self.typing_imports if self.in_type_checking else self.imports

            # Database connection strings heuristics
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
                pass  # Built-in
            elif "mongodb://" in val:
                target_set.add("pymongo")
        self.generic_visit(node)

    def visit_Str(self, node):
        # Python < 3.8 fallback
        self.visit_Constant(node)


def _read_file_safe(filepath):
    # type: (Path) -> Optional[str]
    """
    Reads a file with encoding fallback and size limit.
    Returns file content or None if unreadable.
    """
    try:
        file_size = filepath.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            log("Skipping large file (%d bytes): %s" % (file_size, str(filepath)), level="DEBUG")
            return None
    except OSError:
        return None

    # Try UTF-8 first, then latin-1 as fallback
    for encoding in ("utf-8", "latin-1"):
        try:
            with open(str(filepath), "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            log("Error reading %s: %s" % (str(filepath), str(e)), level="DEBUG")
            return None

    return None


def get_imports_from_notebook(filepath):
    # type: (Path) -> dict
    """
    Parses a Jupyter Notebook (.ipynb) and returns a dict of imports.
    """
    result = {
        "runtime": set(),
        "typing": set(),
        "dynamic": set()
    }  # type: Dict[str, Set[str]]
    try:
        # Size check for notebooks too
        try:
            file_size = filepath.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                log("Skipping large notebook (%d bytes): %s" % (file_size, str(filepath)), level="DEBUG")
                return result
        except OSError:
            return result

        with open(str(filepath), "r", encoding="utf-8") as f:
            notebook = json.load(f)

        # Extract code from all code cells
        code_lines = []
        for cell in notebook.get("cells", []):
            if cell.get("cell_type") == "code":
                source = cell.get("source", [])
                if isinstance(source, str):
                    code_lines.append(source)
                elif isinstance(source, list):
                    code_lines.extend(source)
                code_lines.append("\n")  # Separator

        full_code = "".join(code_lines)

        # Parse compiled code
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
    Parses a python file or notebook and returns a dict of imports:
    {
        "runtime": Set[str],
        "typing": Set[str],
        "dynamic": Set[str]
    }
    """
    if str(filepath).endswith(".ipynb"):
        return get_imports_from_notebook(filepath)

    result = {
        "runtime": set(),
        "typing": set(),
        "dynamic": set()
    }  # type: Dict[str, Set[str]]

    content = _read_file_safe(filepath)
    if content is None:
        return result

    try:
        tree = ast.parse(content, filename=str(filepath))

        visitor = ImportVisitor()
        visitor.visit(tree)

        result["runtime"] = visitor.imports
        result["typing"] = visitor.typing_imports
        result["dynamic"] = visitor.dynamic_imports

    except SyntaxError as e:
        log("Syntax error in %s: %s" % (str(filepath), str(e)), level="ERROR")
    except Exception as e:
        log("Error parsing %s: %s" % (str(filepath), str(e)), level="ERROR")

    return result
