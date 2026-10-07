"""Greeks / Aetherfy Analytics — MCP server.

A Model Context Protocol server that exposes the Greeks options-analytics API as
tools for any MCP client (Claude Desktop, Cursor, …).
"""
from __future__ import annotations

from .server import main, mcp

__all__ = ["main", "mcp"]
__version__ = "0.2.0"
