"""Minimal Python source parser using the built‑in ``ast`` module.

Extracts imports, class definitions (including their methods), and top‑level
function definitions. Errors are captured under the ``error`` key so that the
pipeline can record them in the quality report.
"""

import ast
from pathlib import Path
from typing import Dict, List, Any


def _extract_imports(node: ast.AST) -> List[str]:
    imports: List[str] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Import):
            for alias in child.names:
                imports.append(alias.name)
        elif isinstance(child, ast.ImportFrom):
            module = child.module or ""
            for alias in child.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)
    return imports


def _extract_functions(node: ast.AST) -> List[Dict[str, Any]]:
    funcs: List[Dict[str, Any]] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef):
            funcs.append({
                "name": child.name,
                "lineno": child.lineno,
                "col_offset": child.col_offset,
                "args": [a.arg for a in child.args.args],
            })
    return funcs


def _extract_classes(node: ast.AST) -> List[Dict[str, Any]]:
    classes: List[Dict[str, Any]] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            classes.append({
                "name": child.name,
                "lineno": child.lineno,
                "col_offset": child.col_offset,
                "methods": _extract_functions(child),
            })
    return classes


def parse_python_file(file_path: str) -> Dict[str, Any]:
    """Parse a Python file and return a dict with ``imports``, ``classes`` and ``functions``.

    If parsing fails, the dict contains a single ``error`` key with the exception
    message.
    """
    try:
        source = Path(file_path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=file_path)
        return {
            "imports": _extract_imports(tree),
            "functions": _extract_functions(tree),
            "classes": _extract_classes(tree),
        }
    except Exception as exc:  # pragma: no cover – defensive
        return {"error": str(exc)}
