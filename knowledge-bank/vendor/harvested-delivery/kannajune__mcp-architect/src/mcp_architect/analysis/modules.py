"""Explain a single module/folder: its files, public symbols, and imports."""
from __future__ import annotations

import ast
import re
from pathlib import Path

from .walk import count_loc, iter_files, read_text, rel

_PY = {".py"}
_JS = {".js", ".jsx", ".ts", ".tsx"}

_JS_SYMBOL = re.compile(
    r"^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+([A-Za-z0-9_]+)",
    re.MULTILINE,
)
_JS_IMPORT_SRC = re.compile(r"""from\s*['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]""")


def _py_symbols(text: str) -> tuple[list[str], list[str]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], []
    classes, funcs = [], []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(node.name)
    return classes, funcs


def _py_imports(text: str) -> set[str]:
    out: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out


def explain_module(root: str | Path, module: str = ".") -> dict:
    root = Path(root)
    target = (root / module).resolve()
    if not target.exists():
        return {"error": f"path not found: {module}"}

    base = target if target.is_dir() else target.parent
    files_out = []
    all_imports: set[str] = set()
    total_loc = 0

    paths = [target] if target.is_file() else [
        f for f in iter_files(target) if f.suffix in (_PY | _JS)
    ]
    for f in paths:
        text = read_text(f)
        loc = count_loc(text)
        total_loc += loc
        if f.suffix in _PY:
            classes, funcs = _py_symbols(text)
            all_imports |= _py_imports(text)
        else:
            syms = _JS_SYMBOL.findall(text)
            classes, funcs = [], syms
            for a, b in _JS_IMPORT_SRC.findall(text):
                src = a or b
                if not src.startswith("."):
                    all_imports.add(src.split("/")[0])
        files_out.append({
            "file": rel(f, root),
            "loc": loc,
            "classes": classes,
            "functions": funcs[:25],
        })

    files_out.sort(key=lambda r: r["loc"], reverse=True)
    return {
        "module": rel(target, root) if target != root else ".",
        "files": len(files_out),
        "total_loc": total_loc,
        "external_imports": sorted(i for i in all_imports if i and i.isidentifier()),
        "file_details": files_out[:40],
    }
