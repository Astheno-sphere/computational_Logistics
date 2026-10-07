"""Build an internal module dependency graph and detect import cycles.

Heuristic, dependency-free: full AST for Python, regex for JS/TS. It maps
*internal* imports (modules that resolve to files inside the repo) so you see
how the codebase is wired together — not third-party packages.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from .walk import iter_files, read_text, rel

_PY = {".py"}
_JS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}

_JS_IMPORT = re.compile(
    r"""(?:import\s[^'"]*?from\s*|import\s*|require\(\s*|export\s[^'"]*?from\s*)['"]([^'"]+)['"]""",
)


def _py_module_name(path: Path, root: Path) -> str:
    parts = rel(path, root)[:-3].split("/")  # strip .py
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _collect_python(root: Path) -> dict[str, set[str]]:
    files = [f for f in iter_files(root) if f.suffix in _PY]
    modules = {_py_module_name(f, root): f for f in files}
    # Top-level internal names (packages/modules) to match imports against.
    internal_roots = {m.split(".")[0] for m in modules if m}
    graph: dict[str, set[str]] = {m: set() for m in modules}

    for mod, path in modules.items():
        try:
            tree = ast.parse(read_text(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                targets = [node.module]
            elif isinstance(node, ast.ImportFrom) and node.level:
                # relative import: resolve against current package
                base = mod.split(".")[: -node.level] if mod else []
                mod_part = node.module.split(".") if node.module else []
                targets = [".".join(base + mod_part)]
            for t in targets:
                if not t:
                    continue
                if t.split(".")[0] not in internal_roots:
                    continue
                # match the longest internal module that is a prefix
                best = max(
                    (m for m in modules if t == m or t.startswith(m + ".") or m.startswith(t + ".")),
                    key=len,
                    default=None,
                )
                if best and best != mod:
                    graph[mod].add(best)
    return graph


def _resolve_js(import_path: str, from_file: Path, root: Path, files: set[Path]) -> str | None:
    if not import_path.startswith("."):
        return None  # external package
    target = (from_file.parent / import_path).resolve()
    candidates = [target]
    for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        candidates.append(target.with_suffix(ext))
        candidates.append(target / f"index{ext}")
    for c in candidates:
        if c in files:
            return rel(c, root)
    return None


def _collect_js(root: Path) -> dict[str, set[str]]:
    files = [f for f in iter_files(root) if f.suffix in _JS]
    fileset = {f.resolve() for f in files}
    graph: dict[str, set[str]] = {rel(f, root): set() for f in files}
    for f in files:
        text = read_text(f)
        for m in _JS_IMPORT.finditer(text):
            resolved = _resolve_js(m.group(1), f, root, fileset)
            if resolved and resolved != rel(f, root):
                graph[rel(f, root)].add(resolved)
    return graph


def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    seen_pairs: set[tuple[str, ...]] = set()
    WHITE, GREY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}
    stack: list[str] = []

    def dfs(node: str) -> None:
        color[node] = GREY
        stack.append(node)
        for nxt in graph.get(node, ()):
            if color.get(nxt, BLACK) == GREY:
                cycle = stack[stack.index(nxt):] + [nxt]
                key = tuple(sorted(set(cycle)))
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    cycles.append(cycle)
            elif color.get(nxt, BLACK) == WHITE:
                dfs(nxt)
        stack.pop()
        color[node] = BLACK

    for n in list(graph):
        if color[n] == WHITE:
            dfs(n)
    return cycles


def build_graph(root: str | Path, language: str = "auto") -> dict[str, set[str]]:
    """Return the raw internal-import adjacency: {module: {modules it imports}}."""
    root = Path(root)
    graph: dict[str, set[str]] = {}
    lang = language.lower()
    if lang in ("auto", "python", "py"):
        graph.update(_collect_python(root))
    if lang in ("auto", "js", "ts", "javascript", "typescript"):
        graph.update(_collect_js(root))
    return graph


def get_dependency_graph(root: str | Path, language: str = "auto") -> dict:
    graph = build_graph(root, language)
    root = Path(root)

    edge_count = sum(len(v) for v in graph.values())
    fan_in: dict[str, int] = {}
    for deps in graph.values():
        for d in deps:
            fan_in[d] = fan_in.get(d, 0) + 1
    most_depended = sorted(fan_in.items(), key=lambda kv: kv[1], reverse=True)[:10]
    cycles = _find_cycles(graph)

    return {
        "root": str(root),
        "modules": len(graph),
        "edges": edge_count,
        "most_depended_upon": [{"module": m, "imported_by": c} for m, c in most_depended],
        "cycles": [" -> ".join(c) for c in cycles[:15]],
        "edges_by_module": {k: sorted(v) for k, v in sorted(graph.items()) if v},
    }
