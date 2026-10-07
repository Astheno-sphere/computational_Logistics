"""Tool definitions. Each module exposes ``get_tools() -> list[ToolDef]``.

Tools are thin: they declare a name + JSON input schema and forward to an
isolated worker subprocess. Drop a new module here to add tools — the registry
discovers it automatically.
"""
