# Contributing

Thank you for your interest in contributing to GIS MCP Server! We welcome issues, ideas, docs, and code.

### Ways to contribute

- Report bugs and request features via GitHub Issues
- Improve documentation and examples
- Add or refine MCP tools (Shapely, PyProj, GeoPandas, Rasterio, PySAL)
- Triage issues, review PRs

### Development setup

1. Fork and clone the repo
2. Create a Python 3.10+ virtual environment and install in editable mode:

```bash
pip install uv
uv venv --python=3.10
uv pip install -e .
```

3. Run the server from source:

```bash
python -m gis_mcp
```

4. Optional: integrate with your MCP client for local development

- Claude Desktop (Windows):

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

- Claude Desktop (Linux/Mac):

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

### Pull Request guidelines

- Create a feature branch from main
- Keep edits focused and small; add tests or examples when applicable
- Ensure docs are updated for any user-facing changes
- Follow the project code style and type annotations

### Reporting security issues

Please do not open a public issue. Email the maintainer or use GitHub’s private security advisories.

### License

By contributing, you agree that your contributions are licensed under the repository’s MIT license.
