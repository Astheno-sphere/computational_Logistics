# Related MCP Servers

This page lists other MCP servers that complement GIS MCP Server and can be used together to build comprehensive geospatial AI workflows.

## GeoServer MCP

**Repository:** [mahdin75/geoserver-mcp](https://github.com/mahdin75/geoserver-mcp/)

**Description:** A Model Context Protocol (MCP) server implementation that connects LLMs to the GeoServer REST API.

**Use Cases:**

- Managing GeoServer workspaces and layers
- Querying and updating feature data
- Generating styled map images
- Creating and applying SLD styles

**Key Features:**

- Workspace and layer management
- CQL query support for vector data
- Feature update and deletion operations
- Map generation with custom styles
- SLD style creation and application

**Installation:**

```bash
pip install geoserver-mcp
```

**Documentation:** [GitHub Repository](https://github.com/mahdin75/geoserver-mcp/)

---

## Using Multiple MCP Servers Together

You can configure multiple MCP servers in your client (Claude Desktop or Cursor IDE) to leverage different capabilities:

**Example Configuration (Claude Desktop):**

```json
{
  "mcpServers": {
    "gis-mcp": {
      "command": "/path/to/.venv/bin/gis-mcp",
      "args": []
    },
    "geoserver-mcp": {
      "command": "/path/to/.venv/bin/geoserver-mcp",
      "args": [
        "--url",
        "http://localhost:8080/geoserver",
        "--user",
        "admin",
        "--password",
        "geoserver"
      ]
    }
  }
}
```

This allows your AI assistant to:

- Perform geospatial analysis using GIS MCP Server (Shapely, PyProj, GeoPandas, Rasterio, PySAL)
- Manage and query GeoServer instances using GeoServer MCP
- Combine both capabilities for comprehensive geospatial workflows

---

## Contributing

Know of another MCP server that complements GIS MCP Server? We'd love to add it to this list! Please open an issue or submit a pull request with the details.
