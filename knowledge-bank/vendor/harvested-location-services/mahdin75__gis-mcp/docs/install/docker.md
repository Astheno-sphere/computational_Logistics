# Docker Installation

### Install via Docker

GIS MCP Server can be run using Docker, which provides an isolated environment with all dependencies pre-installed.

**Important:** Both `Dockerfile` and `Dockerfile.local` have **HTTP transport mode enabled by default**. The server runs on port `9010` and is accessible at `http://localhost:9010/mcp`.

#### Using Dockerfile

The main `Dockerfile` installs the package from PyPI:

1. Build the Docker image:

```bash
docker build -t gis-mcp .
```

2. Run the container (HTTP mode is enabled by default):

```bash
docker run -p 9010:9010 gis-mcp
```

The server will be available at `http://localhost:9010/mcp` in HTTP transport mode.

#### Using Dockerfile.local

The `Dockerfile.local` installs the package from local source files (useful for development or custom builds):

1. Build the Docker image:

```bash
docker build -f Dockerfile.local -t gis-mcp:local .
```

2. Run the container (HTTP mode is enabled by default):

```bash
docker run -p 9010:9010 gis-mcp:local
```

The server will be available at `http://localhost:9010/mcp` in HTTP transport mode.

#### Environment Variables

Both Dockerfiles set the following environment variables by default:

- `GIS_MCP_TRANSPORT=http` - HTTP transport mode is enabled by default
- `GIS_MCP_HOST=0.0.0.0` - HTTP server host
- `GIS_MCP_PORT=9010` - HTTP server port

You can override these by setting environment variables when running the container.

#### Running in STDIO Mode

To use STDIO transport instead of HTTP, override the transport environment variable:

```bash
docker run -e GIS_MCP_TRANSPORT=stdio gis-mcp
```

#### Running in HTTP Mode (Default)

HTTP transport is the default in Docker. Simply expose the port:

```bash
docker run -p 9010:9010 gis-mcp
```

Or with custom host and port:

```bash
docker run -e GIS_MCP_HOST=0.0.0.0 -e GIS_MCP_PORT=9000 -p 9000:9000 gis-mcp
```

#### Client Configuration

For HTTP transport mode, configure your MCP client to connect to:

```
http://localhost:9010/mcp
```

For STDIO transport mode, configure your client to run the Docker container:

```json
{
  "mcpServers": {
    "gis-mcp": {
      "command": "docker",
      "args": ["run", "-i", "gis-mcp"]
    }
  }
}
```

#### Persistent Storage with Docker Volumes

By default, data written inside a Docker container is ephemeral and will be lost when the container is removed. To persist your GIS data, you should mount a volume to the container's storage directory.

**Mount a host directory as a volume:**

```bash
docker run -p 9010:9010 \
  -v /path/on/host:/app/.gis_mcp/data \
  gis-mcp
```

**Use a named Docker volume:**

```bash
# Create a named volume
docker volume create gis-mcp-data

# Run container with the named volume
docker run -p 9010:9010 \
  -v gis-mcp-data:/app/.gis_mcp/data \
  gis-mcp
```

**Custom storage path with volume mount:**

If you want to use a custom storage path inside the container, you can combine volume mounting with the `--storage-path` argument:

```bash
docker run -p 9010:9010 \
  -v /path/on/host:/custom/storage \
  -e GIS_MCP_STORAGE_PATH=/custom/storage \
  gis-mcp
```

Or using a named volume:

```bash
docker run -p 9010:9010 \
  -v gis-mcp-data:/custom/storage \
  -e GIS_MCP_STORAGE_PATH=/custom/storage \
  gis-mcp
```

**Example with docker-compose:**

```yaml
version: "3.8"

services:
  gis-mcp:
    image: gis-mcp:latest
    ports:
      - "9010:9010"
    volumes:
      - gis-mcp-data:/app/.gis_mcp/data
    environment:
      - GIS_MCP_TRANSPORT=http
      - GIS_MCP_HOST=0.0.0.0
      - GIS_MCP_PORT=9010

volumes:
  gis-mcp-data:
```

**Benefits of using volumes:**

- **Data persistence:** Your GIS data, downloaded files, and outputs survive container restarts and removals
- **Performance:** Named volumes are managed by Docker and can offer better performance
- **Backup:** Easy to backup by copying the volume or host directory
- **Sharing:** Multiple containers can share the same volume if needed

For more details on storage configuration, see the [Storage Configuration](../storage-configuration.md) documentation.

#### Notes

- The Dockerfiles use Python 3.12 and include all system dependencies (GDAL, PROJ, GEOS)
- Both `Dockerfile` and `Dockerfile.local` install the package with all extras (`[all]`)
- **HTTP transport mode is enabled by default** in both Dockerfiles
- The default port is `9010` in both Dockerfiles
- For production deployments, consider using specific image tags instead of `latest`
- **Always use volumes for persistent storage** to avoid data loss when containers are removed
- For more details on transport modes, see the [HTTP Transport Configuration](../http-transport.md) documentation
