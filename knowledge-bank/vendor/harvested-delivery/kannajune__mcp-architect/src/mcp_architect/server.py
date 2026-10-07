"""MCP server exposing codebase-architecture tools to any MCP client.

Run with:  mcp-architect            (stdio transport, for Claude Desktop / Cursor)
"""
from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .analysis import (
    analyze_impact,
    explain_module,
    find_hotspots,
    get_dependency_graph,
    get_overview,
)

mcp = FastMCP("mcp-architect")

# Optional: pin analysis to a fixed project so clients can omit `path`.
_ROOT_ENV = os.environ.get("MCP_ARCHITECT_ROOT")


def _resolve(path: str) -> Path:
    base = Path(_ROOT_ENV).expanduser() if _ROOT_ENV else Path.cwd()
    p = (base / path).expanduser() if not os.path.isabs(path) else Path(path)
    return p.resolve()


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "_none_"


@mcp.tool()
def architecture_overview(path: str = ".") -> str:
    """High-level map of a codebase: languages, frameworks, size, structure, and
    entry points. Start here to understand an unfamiliar repo.

    Args:
        path: Repo path to analyze. Relative to the server's working directory
              (or MCP_ARCHITECT_ROOT if set). Defaults to the whole project.
    """
    root = _resolve(path)
    if not root.is_dir():
        return f"❌ Not a directory: {root}"
    d = get_overview(root)
    langs = "\n".join(
        f"- **{l['language']}** — {l['files']} files, {l['loc']:,} LOC"
        for l in d["languages"][:8]
    ) or "_no source files detected_"
    return (
        f"# Architecture Overview — `{root.name}`\n\n"
        f"**{d['total_files']:,} files · {d['total_code_loc']:,} lines of code**\n\n"
        f"## Languages\n{langs}\n\n"
        f"## Ecosystems\n{_bullets(d['ecosystems'])}\n\n"
        f"## Frameworks / key libraries\n{_bullets(d['frameworks'])}\n\n"
        f"## Top-level structure\n{_bullets(d['top_level_dirs'])}\n\n"
        f"## Entry points\n{_bullets(d['entry_points'])}\n"
    )


@mcp.tool()
def dependency_graph(path: str = ".", language: str = "auto") -> str:
    """Map how internal modules import each other, the most-depended-upon
    modules, and any circular dependencies. Use to understand coupling.

    Args:
        path: Repo path to analyze.
        language: 'auto', 'python', or 'js'/'ts'.
    """
    root = _resolve(path)
    if not root.is_dir():
        return f"❌ Not a directory: {root}"
    d = get_dependency_graph(root, language)
    hubs = "\n".join(
        f"- `{m['module']}` — imported by {m['imported_by']} modules"
        for m in d["most_depended_upon"]
    ) or "_none_"
    cycles = (
        "\n".join(f"- 🔁 {c}" for c in d["cycles"])
        if d["cycles"] else "✅ _no circular dependencies found_"
    )
    return (
        f"# Dependency Graph — `{root.name}`\n\n"
        f"**{d['modules']} modules · {d['edges']} internal import edges**\n\n"
        f"## Most depended-upon (architectural hubs)\n{hubs}\n\n"
        f"## Circular dependencies\n{cycles}\n"
    )


@mcp.tool()
def impact_analysis(target: str = "", path: str = ".", language: str = "auto") -> str:
    """What could break if you change `target`? Walks the import graph backwards
    to list direct importers and the full transitive blast radius, and flags
    whether the target is a high-risk hub. Use before editing/refactoring a module.

    Args:
        target: Module or file to analyze, e.g. "app/core/db.py" or "app.core.db".
                If omitted, returns the highest-impact modules to pick from.
        path: Repo root.
        language: 'auto', 'python', or 'js'/'ts'.
    """
    root = _resolve(path)
    if not root.is_dir():
        return f"❌ Not a directory: {root}"
    if not target.strip():
        dg = get_dependency_graph(root, language)
        hubs = "\n".join(
            f"- `{m['module']}` — imported by {m['imported_by']} modules"
            for m in dg["most_depended_upon"][:5]
        ) or "_no internal dependencies found_"
        return (
            "ℹ️ `impact_analysis` needs a **target** — the module or file you're about "
            "to change, e.g. `app/core/db.py` or `app.core.db`.\n\n"
            "Highest-impact modules worth checking first:\n" + hubs
        )
    d = analyze_impact(root, target, language)
    if not d["found"]:
        hint = (
            "\n\nDid you mean:\n" + "\n".join(f"- `{m}`" for m in d["suggestions"])
            if d.get("suggestions") else ""
        )
        return f"❌ Couldn't find `{d['target']}` in the import graph.{hint}"

    risk = (
        "⚠️ **High-risk hub** — many modules depend on this; change carefully and test broadly."
        if d["is_hub"] else "✅ Limited blast radius — relatively safe to change."
    )
    direct = "\n".join(f"- `{m}`" for m in d["direct_importers"][:30]) or "_none — nothing imports this_"
    trans = "\n".join(f"- `{m}`" for m in d["transitive_importers"][:30]) or "_none_"
    more = (
        f"\n…and {d['transitive_count'] - 30} more"
        if d["transitive_count"] > 30 else ""
    )
    return (
        f"# Impact of changing `{d['target']}`\n\n"
        f"{risk}\n\n"
        f"**Direct importers: {d['direct_count']} · "
        f"Transitive blast radius: {d['transitive_count']} of {d['total_modules']} modules**\n\n"
        f"## Direct importers\n{direct}\n\n"
        f"## Full blast radius (transitive)\n{trans}{more}\n"
    )


@mcp.tool()
def hotspots(path: str = ".", top: int = 10) -> str:
    """Find the files most worth attention: largest, most complex, most
    frequently changed (git), and highest combined risk.

    Args:
        path: Repo path to analyze.
        top: How many files per category (default 10).
    """
    root = _resolve(path)
    if not root.is_dir():
        return f"❌ Not a directory: {root}"
    d = find_hotspots(root, top)
    risk = "\n".join(
        f"- `{r['file']}` — {r['loc']} LOC, complexity {r['complexity']}, "
        f"{r['changes']} changes" for r in d["highest_risk"]
    ) or "_none_"
    largest = "\n".join(f"- `{r['file']}` — {r['loc']} LOC" for r in d["largest"])
    note = "" if d["git_history_available"] else (
        "\n> ℹ️ No git history found, so change-frequency is unavailable.\n"
    )
    return (
        f"# Hotspots — `{root.name}`\n\n"
        f"_{d['files_analyzed']} source files analyzed._{note}\n"
        f"## Highest risk (big + complex + churny)\n{risk}\n\n"
        f"## Largest files\n{largest}\n"
    )


@mcp.tool()
def explain(path: str = ".", module: str = ".") -> str:
    """Deep-dive a single folder or file: its files, public classes/functions,
    and external dependencies.

    Args:
        path: Repo root.
        module: Sub-path within the repo (folder or file) to explain.
    """
    root = _resolve(path)
    if not root.exists():
        return f"❌ Path not found: {root}"
    d = explain_module(root, module)
    if "error" in d:
        return f"❌ {d['error']}"
    details = "\n".join(
        f"- `{f['file']}` ({f['loc']} LOC)"
        + (f" — classes: {', '.join(f['classes'])}" if f["classes"] else "")
        + (f" — functions: {', '.join(f['functions'][:8])}" if f["functions"] else "")
        for f in d["file_details"]
    ) or "_no source files_"
    return (
        f"# Module — `{d['module']}`\n\n"
        f"**{d['files']} files · {d['total_loc']:,} LOC**\n\n"
        f"## External dependencies\n{_bullets(d['external_imports'][:25])}\n\n"
        f"## Files & symbols\n{details}\n"
    )


def main() -> None:
    """Console-script entry point (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
