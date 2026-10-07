# PIP

### Install via pip (with uv)

This video teaches you the installation of GIS MCP Server on your windows and Claude Desktop:

<iframe width="560" height="315" src="https://www.youtube.com/embed/1u_ra1Wp4es" frameborder="0" allowfullscreen></iframe>

1. Install uv and create a virtual environment (Python 3.10+):

```bash
pip install uv
uv venv --python=3.10
```

2. Install the package:

```bash
uv pip install gis-mcp
```

### Install with visualization features

To install with visualization capabilities (Folium and PyDeck for interactive maps):

```bash
uv pip install gis-mcp[visualize]
```

This will install additional dependencies:

- `folium>=0.15.0` - For creating interactive web maps
- `pydeck>=0.9.0` - For advanced 3D visualizations

3. Run the server:

```bash
gis-mcp
```

By default, the server runs in **STDIO transport mode**, which is ideal for local development and integration with Claude Desktop or Cursor IDE.

You can also run the server in **HTTP transport mode** for network deployments:

```bash
export GIS_MCP_TRANSPORT=http
export GIS_MCP_PORT=8080
gis-mcp
```

For more details on transport modes (STDIO vs HTTP), see the [HTTP Transport Configuration](../http-transport.md) documentation.

### Client configuration for pip installs

Claude Desktop (Windows):

```json
{
  "mcpServers": {
    "gis-mcp": {
      "command": "C:\\Users\\YourUsername\\.venv\\Scripts\\gis-mcp",
      "args": []
    }
  }
}
```

Claude Desktop (Linux/Mac):

```json
{
  "mcpServers": {
    "gis-mcp": {
      "command": "/home/YourUsername/.venv/bin/gis-mcp",
      "args": []
    }
  }
}
```

Cursor IDE (Windows) – `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "gis-mcp": {
      "command": "C:\\Users\\YourUsername\\.venv\\Scripts\\gis-mcp",
      "args": []
    }
  }
}
```

Cursor IDE (Linux/Mac) – `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "gis-mcp": {
      "command": "/home/YourUsername/.venv/bin/gis-mcp",
      "args": []
    }
  }
}
```

Notes:

- Replace `YourUsername` with your actual user name
- Restart your IDE after adding configuration
