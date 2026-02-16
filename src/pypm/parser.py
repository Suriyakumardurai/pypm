import ast
from pathlib import Path
from typing import Set
from .utils import log

class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name.split('.')[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            # Handle "from . import module" (node.module is None)
            # node.module is the "package.module" part
            self.imports.add(node.module.split('.')[0])
        self.generic_visit(node)
        
    def visit_Constant(self, node):
        # Scan string literals for database connection strings
        if isinstance(node.value, str):
            val = node.value
            if "mysql" + "+aiomysql://" in val:
                self.imports.add("aiomysql")
            elif "postgresql" + "+asyncpg://" in val:
                self.imports.add("asyncpg")
            elif "postgresql" + "+psycopg2://" in val:
                self.imports.add("psycopg2")
            elif "mssql" + "+pyodbc://" in val:
                self.imports.add("pyodbc")
        self.generic_visit(node)
        
    def visit_Str(self, node):
        # Python < 3.8 fallback
        self.visit_Constant(node)

def get_imports_from_file(filepath: Path) -> Set[str]:
    """
    Parses a python file and returns a set of top-level import names.
    """
    imports = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(filepath))
            
        visitor = ImportVisitor()
        visitor.visit(tree)
        imports = visitor.imports
                    
    except SyntaxError as e:
        log(f"Syntax error in {filepath}: {e}", level="ERROR")
    except Exception as e:
        log(f"Error parsing {filepath}: {e}", level="ERROR")
        
    return imports
