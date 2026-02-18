import ast
from pathlib import Path
from typing import Set
from .utils import log

class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()
        self.typing_imports = set()
        self.dynamic_imports = set()
        self.in_type_checking = False

    def visit_Import(self, node):
        for alias in node.names:
            # Add base module
            base_module = alias.name.split('.')[0]
            
            if self.in_type_checking:
                self.typing_imports.add(base_module)
                self.typing_imports.add(alias.name) # Full path for namespaces
            else:
                self.imports.add(base_module)
                self.imports.add(alias.name) # Full path for namespaces
            
            # Add full import path for extra inference (if not typing)
            # CHANGE: Only add base module to prevent "fastapi.Depends" being treated as a package.
            # Submodule logic should be handled by resolver if needed, but for now we trust base package.
            
            # if '.' in alias.name:
            #     if self.in_type_checking:
            #         self.typing_imports.add(alias.name)
            #     else:
            #         self.imports.add(alias.name)

        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        # Ignore relative imports (level > 0)
        if node.level > 0:
            return

        target_set = self.typing_imports if self.in_type_checking else self.imports

        if node.module:
            # Handle "from module import submodule"
            # node.module is the "module" part
            base_module = node.module.split('.')[0]
            target_set.add(base_module)
            target_set.add(node.module) # Full path for namespaces (from X import Y)
            
            # Add full path for submodule inference
            # CHANGE: Removed to prevent submodule pollution.
            # e.g. from pipecat import aws -> pipecat.aws -> INVALID package unless mapped.
            # Resolver logic for "pipecat.aws" mapping relied on this, but it causes too many false positives.
            # We will rely on base package detection.
            # for alias in node.names:
            #    target_set.add(f"{node.module}.{alias.name}")

        self.generic_visit(node)

    def visit_If(self, node):
        # Detect "if TYPE_CHECKING:" blocks
        # We look for a Name node with id="TYPE_CHECKING" in the test
        is_type_checking = False
        try:
           # Simple check: if TYPE_CHECKING:
           if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
               is_type_checking = True
           # Complex check: if typing.TYPE_CHECKING:
           elif isinstance(node.test, ast.Attribute) and node.test.attr == "TYPE_CHECKING":
               is_type_checking = True
        except Exception:
            pass

        if is_type_checking:
            prev_state = self.in_type_checking
            self.in_type_checking = True
            # Visit body with flag set
            for child in node.body:
                self.visit(child)
            self.in_type_checking = prev_state
            
            # Visit orelse (dependencies in else are definitely runtime)
            for child in node.orelse:
                self.visit(child)
        else:
            self.generic_visit(node)

    def visit_Call(self, node):
        # Detect dynamic imports:
        # importlib.import_module("pkg")
        # __import__("pkg")
        try:
            module_name = None
            if isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                # Check for importlib.import_module
                # We can't easily verify the base is importlib without more context, but "import_module" is strong signal.
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
                if "aiomysql" in val: target_set.add("aiomysql")
                elif "pymysql" in val: target_set.add("pymysql")
                else: target_set.add("mysqlclient") # Default for mysql://
                
            elif "postgres" in val and ("://" in val or "+asyncpg" in val or "+psycopg" in val):
                if "asyncpg" in val: target_set.add("asyncpg")
                elif "psycopg" in val: target_set.add("psycopg2-binary") # Default
                else: target_set.add("psycopg2-binary") # Default for postgres://
                
            elif "mssql" in val and ("://" in val or "+pyodbc" in val):
                target_set.add("pyodbc")
                
            elif "redis://" in val:
                target_set.add("redis")
            elif "sqlite://" in val:
                pass # Built-in
            elif "mongodb://" in val:
                target_set.add("pymongo")
        self.generic_visit(node)
        
    def visit_Str(self, node):
        # Python < 3.8 fallback
        self.visit_Constant(node)

import json

def get_imports_from_notebook(filepath: Path) -> dict:
    """
    Parses a Jupyter Notebook (.ipynb) and returns a dict of imports.
    """
    result = {
        "runtime": set(),
        "typing": set(),
        "dynamic": set()
    }
    try:
        with open(filepath, "r", encoding="utf-8") as f:
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
                code_lines.append("\n") # Separator
                
        full_code = "".join(code_lines)
        
        # Parse compiled code
        tree = ast.parse(full_code, filename=str(filepath))
        visitor = ImportVisitor()
        visitor.visit(tree)
        
        result["runtime"] = visitor.imports
        result["typing"] = visitor.typing_imports
        result["dynamic"] = visitor.dynamic_imports
        
    except Exception as e:
        log(f"Error parsing notebook {filepath}: {e}", level="ERROR")
        
    return result

def get_imports_from_file(filepath: Path) -> dict:
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
    }
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(filepath))
            
        visitor = ImportVisitor()
        visitor.visit(tree)
        
        result["runtime"] = visitor.imports
        result["typing"] = visitor.typing_imports
        result["dynamic"] = visitor.dynamic_imports
                    
    except SyntaxError as e:
        log(f"Syntax error in {filepath}: {e}", level="ERROR")
    except Exception as e:
        log(f"Error parsing {filepath}: {e}", level="ERROR")
        
    return result
