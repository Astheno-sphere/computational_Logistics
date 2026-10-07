"""Auto-discover tool definitions from ``mikeplus_mcp.tools``.

Each module under ``tools/`` exposes ``get_tools() -> list[ToolDef]``. To add a
new tool, drop a module there (or extend an existing one) — the server registers
it automatically; no edits to ``server.py`` are needed.
"""
from __future__ import annotations

import importlib
import pkgutil

from ._types import ToolDef
from . import tools as _tools_pkg


def discover_tools() -> list[ToolDef]:
    found: list[ToolDef] = []
    for info in pkgutil.iter_modules(_tools_pkg.__path__):
        mod = importlib.import_module(f"{_tools_pkg.__name__}.{info.name}")
        getter = getattr(mod, "get_tools", None)
        if callable(getter):
            found.extend(getter())
    return found
