# HTTP Transport Configuration

The GIS MCP server now supports both STDIO and HTTP transport modes, making it flexible for different deployment scenarios.

## Transport Modes

### STDIO Transport (Default)

- **Use case**: Local development, Claude Desktop integration, command-line tools
- **Behavior**: Server communicates through standard input/output streams
- **Client connection**: One client per server process

### HTTP Transport

- **Use case**: Network deployment, multiple clients, web service integration
- **Behavior**: Server runs as HTTP web service
- **Client connection**: Multiple concurrent clients supported
- **Endpoints**:
  - MCP endpoint: `http://host:port/mcp`
  - Storage endpoints: `http://host:port/storage/*` (upload, download, list)

See [Server Endpoints](endpoints.md) for detailed endpoint documentation.

## Configuration

The transport mode is controlled by environment variables:

| Variable            | Default   | Description                               |
| ------------------- | --------- | ----------------------------------------- |
| `GIS_MCP_TRANSPORT` | `stdio`   | Transport mode: `stdio` or `http`         |
| `GIS_MCP_HOST`      | `0.0.0.0` | HTTP server host (only used in HTTP mode) |
| `GIS_MCP_PORT`      | `8080`    | HTTP server port (only used in HTTP mode) |

## Usage Examples

### Default STDIO Mode

```bash
# No environment variables needed
gis-mcp

# Or explicitly set
export GIS_MCP_TRANSPORT=stdio
gis-mcp
```

### HTTP Mode

```bash
# Basic HTTP mode (uses defaults: 0.0.0.0:8080)
export GIS_MCP_TRANSPORT=http
gis-mcp

# Custom host and port
export GIS_MCP_TRANSPORT=http
export GIS_MCP_HOST=127.0.0.1
export GIS_MCP_PORT=9000
gis-mcp

# One-liner
GIS_MCP_TRANSPORT=http GIS_MCP_HOST=localhost GIS_MCP_PORT=8000 gis-mcp
```

## Docker Usage

**Note:** Both `Dockerfile` and `Dockerfile.local` have **HTTP transport mode enabled by default** with port `9010`.

### HTTP Mode (Default in Docker)

```bash
# HTTP mode is the default - just expose the port
docker run -p 9010:9010 your-gis-mcp-image

# Custom port
docker run -e GIS_MCP_PORT=9000 -p 9000:9000 your-gis-mcp-image
```

The server will be available at:

- **MCP endpoint**: `http://localhost:9010/mcp` (or your custom port)
- **Storage endpoints**: `http://localhost:9010/storage/*`

See [Server Endpoints](endpoints.md) for complete endpoint documentation.

### STDIO Mode

```bash
# Override to use STDIO transport instead
docker run -e GIS_MCP_TRANSPORT=stdio your-gis-mcp-image
```

## Client Connection

### STDIO Mode

Clients spawn the server process directly:

```json
{
  "command": "gis-mcp",
  "args": []
}
```

### HTTP Mode

Clients connect to the HTTP endpoints:

- **MCP endpoint**: `http://your-server:8080/mcp`
- **Storage endpoints**: `http://your-server:8080/storage/*`

For detailed endpoint documentation, see [Server Endpoints](endpoints.md).

## Backward Compatibility

This implementation maintains full backward compatibility:

- Existing deployments continue to work without changes
- Default behavior remains STDIO transport
- No breaking changes to the API

## Troubleshooting

### Common Issues

1. **Port already in use**

   ```
   Error: [Errno 48] Address already in use
   ```

   Solution: Change the port using `GIS_MCP_PORT` environment variable

2. **Permission denied on port < 1024**

   ```
   Error: [Errno 13] Permission denied
   ```

   Solution: Use a port number >= 1024 or run with appropriate privileges

3. **Cannot connect to HTTP endpoint**
   - Verify the server is running in HTTP mode
   - Check firewall settings
   - Ensure the correct host/port configuration

### Debug Mode

Enable debug logging for troubleshooting:

```bash
gis-mcp --debug
```

## Security Considerations

When using HTTP transport:

- Consider using `GIS_MCP_HOST=127.0.0.1` for localhost-only access
- Use `GIS_MCP_HOST=0.0.0.0` only when you need external network access
- Implement proper network security (firewalls, VPNs) for production deployments
- The HTTP transport uses the MCP protocol over HTTP, which includes built-in security features
