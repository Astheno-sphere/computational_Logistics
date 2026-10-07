# Server Endpoints

When running the GIS MCP server in HTTP or SSE transport mode, the following endpoints are available:

## MCP Endpoints

### `/mcp` (HTTP Transport)

- **Method**: POST
- **Content-Type**: application/json
- **Description**: Main MCP JSON-RPC endpoint for HTTP transport
- **Usage**: Used by MCP clients to communicate with the server via HTTP POST requests

### `/sse` (SSE Transport)

- **Method**: GET
- **Content-Type**: text/event-stream
- **Description**: Server-Sent Events endpoint for SSE transport
- **Usage**: Used by MCP clients for real-time streaming communication

## Storage Endpoints

The storage endpoints allow clients to upload, download, and list files on the server's storage directory.

### `POST /storage/upload`

Upload a file to the server's storage directory.

**Request:**

- **Content-Type**: `multipart/form-data`
- **Form Fields**:
  - `file` (required): The file to upload
  - `path` (optional): Remote path where the file should be saved (defaults to filename)

**Response:**

```json
{
  "remote_path": "output.gpkg",
  "size": 12345,
  "message": "File uploaded successfully to output.gpkg"
}
```

**Example using curl:**

```bash
curl -X POST http://localhost:8080/storage/upload \
  -F "file=@local_file.gpkg" \
  -F "path=output.gpkg"
```

**Example using Python requests:**

```python
import requests

with open('local_file.gpkg', 'rb') as f:
    files = {'file': ('local_file.gpkg', f, 'application/octet-stream')}
    data = {'path': 'output.gpkg'}
    response = requests.post('http://localhost:8080/storage/upload', files=files, data=data)
    print(response.json())
```

### `GET /storage/download`

Download a file from the server's storage directory.

**Request:**

- **Query Parameters**:
  - `path` (required): Path to the file to download

**Response:**

- **Content-Type**: `application/octet-stream`
- **Body**: File content

**Example using curl:**

```bash
curl -O http://localhost:8080/storage/download?path=output.gpkg
```

**Example using Python requests:**

```python
import requests

response = requests.get('http://localhost:8080/storage/download', params={'path': 'output.gpkg'})
with open('downloaded_file.gpkg', 'wb') as f:
    f.write(response.content)
```

### `GET /storage/list`

List files in the server's storage directory.

**Request:**

- **Query Parameters**:
  - `path` (optional): Directory path to list (defaults to storage root)

**Response:**

```json
{
  "files": [
    {
      "name": "output.gpkg",
      "path": "output.gpkg",
      "size": 12345,
      "type": "file",
      "modified": 1234567890.0
    },
    {
      "name": "subfolder",
      "path": "subfolder",
      "size": null,
      "type": "directory",
      "modified": 1234567890.0
    }
  ],
  "path": "/"
}
```

**Example using curl:**

```bash
curl http://localhost:8080/storage/list?path=outputs
```

**Example using Python requests:**

```python
import requests

response = requests.get('http://localhost:8080/storage/list', params={'path': 'outputs'})
files = response.json()
for file in files['files']:
    print(f"{file['name']} ({file['type']})")
```

## Endpoint Availability

The endpoints are only available when the server is running in HTTP or SSE transport mode:

- **STDIO mode**: No HTTP endpoints available (server communicates via stdin/stdout)
- **HTTP mode**: `/mcp` and `/storage/*` endpoints available
- **SSE mode**: `/sse` and `/storage/*` endpoints available

## Storage Path

Files are stored in the configured storage directory:

- **Default**: `~/.gis_mcp/data/`
- **Configurable**: Set via `GIS_MCP_STORAGE_PATH` environment variable or `--storage-path` CLI argument

Relative paths in storage operations are resolved relative to this storage directory. Absolute paths are used as-is.

## Example Workflow

1. **Upload a file:**

   ```bash
   curl -X POST http://localhost:8080/storage/upload \
     -F "file=@input.shp" \
     -F "path=input.shp"
   ```

2. **Process the file using MCP tools** (via `/mcp` or `/sse` endpoint)

3. **List available files:**

   ```bash
   curl http://localhost:8080/storage/list
   ```

4. **Download the result:**
   ```bash
   curl -O http://localhost:8080/storage/download?path=output.gpkg
   ```

## Error Responses

All endpoints return appropriate HTTP status codes:

- **200 OK**: Success
- **400 Bad Request**: Invalid request (missing parameters, invalid data)
- **404 Not Found**: File or path not found
- **500 Internal Server Error**: Server error

Error responses include a JSON body with error details:

```json
{
  "error": "File not found: output.gpkg",
  "message": "File not found: output.gpkg"
}
```
