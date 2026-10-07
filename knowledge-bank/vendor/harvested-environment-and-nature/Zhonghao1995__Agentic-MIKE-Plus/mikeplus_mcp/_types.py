"""Shared lightweight types (kept import-cheap and dependency-free)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class ToolDef:
    """One MCP tool: its public schema + a handler that returns a JSON-able dict."""
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], dict]
