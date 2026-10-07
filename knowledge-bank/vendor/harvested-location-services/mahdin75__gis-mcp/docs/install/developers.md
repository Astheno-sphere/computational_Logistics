# Dev install

### Development install (editable)

1. Create env and install in editable mode:

```bash
pip install uv
uv venv --python=3.10
uv pip install -e .
```

2. Run the server from source:

```bash
python -m gis_mcp
```

### Development client configuration

Claude Desktop (Windows):

```json
{
  "mcpServers": {
    "gis-mcp": {
      "command": "C:\\path\\to\\gis-mcp\\.venv\\Scripts\\python",
      "args": ["-m", "gis_mcp"]
    }
  }
}
```

Claude Desktop (Linux/Mac):

```json
{
  "mcpServers": {
    "gis-mcp": {
      "command": "/path/to/gis-mcp/.venv/bin/python",
      "args": ["-m", "gis_mcp"]
    }
  }
}
```

Cursor IDE (Windows) – `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "gis-mcp": {
      "command": "C:\\path\\to\\gis-mcp\\.venv\\Scripts\\python",
      "args": ["-m", "gis_mcp"]
    }
  }
}
```

Cursor IDE (Linux/Mac) – `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "gis-mcp": {
      "command": "/path/to/gis-mcp/.venv/bin/python",
      "args": ["-m", "gis_mcp"]
    }
  }
}
```

Notes:

- Ensure paths point to your actual environment/project
- Restart the IDE to apply changes
