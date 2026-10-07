"""Pure, dependency-free codebase-analysis functions.

These are intentionally decoupled from MCP so they can be unit-tested and
reused on their own.
"""
from .deps import build_graph, get_dependency_graph
from .hotspots import find_hotspots
from .impact import analyze_impact
from .modules import explain_module
from .stack import get_overview

__all__ = [
    "get_overview",
    "get_dependency_graph",
    "build_graph",
    "analyze_impact",
    "find_hotspots",
    "explain_module",
]
