# Ambee MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Node.js >= 18](https://img.shields.io/badge/node-%3E%3D18-brightgreen)](https://nodejs.org)

The official [Model Context Protocol](https://modelcontextprotocol.io) server for [Ambee](https://www.getambee.com). It gives any MCP-compatible AI assistant — Claude, ChatGPT, Cursor, VS Code, Ollama, and more — direct access to live **air quality**, **pollen**, and **weather** data.

Point your assistant at this server and it can answer questions like *"Is it a bad tree pollen day in Atlanta?"* or *"Should we move the Saturday offsite indoors?"* by calling Ambee's data directly, instead of guessing from stale training data.

Looking for a ready to access server? Try our host [Ambee MCP](https://docs.ambeedata.com/mcp/overview)

## Table of contents

- [Tools](#tools)
- [Error handling](#error-handling)
- [Requirements](#requirements)
- [Install](#install)
- [Configure](#configure)
- [Run standalone](#run-standalone)
- [Connect a client](#connect-a-client)
- [Example prompts](#example-prompts)
- [Support](#support)
- [Contributing](#contributing)
- [License](#license)

## Tools

Six tools — latest conditions and a 48-hour forecast for each of the three datasets:

| Tool | Endpoint | Returns |
| --- | --- | --- |
| `air_quality_latest` | `GET /v3/aq/latest` | AQI + CO/NO2/O3/PM10/PM2.5/SO2, dominant pollutant, category. 1 record. |
| `air_quality_forecast` | `GET /v3/aq/forecast/48hrs` | Same fields, hourly. Up to 48 records. |
| `weather_latest` | `GET /v3/weather/latest` | Temperature, apparent temp, humidity, dew point, pressure, cloud cover, precipitation, wind, UV index, ozone, visibility, summary. 1 record. |
| `weather_forecast` | `GET /v3/weather/forecast/48hrs` | Same fields, hourly. Up to 48 records. |
| `pollen_latest` | `GET /v3/pollen/latest` | Tree/grass/weed counts + risk levels, optional per-species breakdown. 1 record. |
| `pollen_forecast` | `GET /v3/pollen/forecast/48hrs` | Same fields, hourly. Up to 48 records. |

Every tool accepts **either**:
- `lat` + `lng` (numbers), **or**
- `place` (free text, e.g. `"Bengaluru"`)

Sending both, or neither, is rejected client-side before any request is made. All `/v3` endpoints accept `place` natively, so no separate geocoding step is needed.

Optional parameters:
- `locale` (boolean) — adds a `localTime` field to each record.
- `aqiStandard` (air quality only) — `EPA` (default), `IN`, `UK`, `CN`, or `CA`.
- `units` (weather only) — `imperial` (default), `metric`, or `si`.
- `speciesRisk` (pollen only) — include per-species risk levels where the region supports it.

## Error handling

Every response is checked against [Ambee's documented status codes](https://docs.ambeedata.com/apis/overview#error-codes):

| Code | Meaning | How this server handles it |
| --- | --- | --- |
| 200 | OK | Returned as normal tool output. |
| 206 | Partial data (quota ran out mid-response) | Returned as usable data, with a `warning` field explaining it's trimmed. |
| 400 | Bad request | Returned as a tool error explaining likely cause (missing/invalid params). |
| 401 | Unauthorized | Returned as a tool error — check `AMBEE_API_KEY`. |
| 403 | Forbidden | Returned as a tool error — key lacks permission for this endpoint. |
| 404 | Not found | Returned as a tool error — no data for that location. |
| 422 | Quota exceeded | Returned as a tool error — plan quota hit. |
| 429 | Rate limited | Returned as a tool error — back off and retry. |
| 500 | Internal server error | Returned as a tool error — retry later. |
| 299 | Deprecated | Returned as a tool error — endpoint/feature not supported. |

Every non-2xx response comes back as an MCP tool error (`isError: true`) with a human-readable message combining Ambee's own error text and a short hint on what to do next, so the calling assistant can explain the failure instead of just surfacing a raw status code.

## Requirements

- Node.js 18+
- An Ambee API key — get one free at the [Ambee API dashboard](https://api-dashboard.getambee.com)

## Install

```bash
git clone https://github.com/getambee/ambee-mcp-server.git
cd ambee-mcp-server
npm install
```

## Configure

```bash
export AMBEE_API_KEY="your-ambee-api-key"
```

Never commit your key or put it in a config file that goes into version control. See [SECURITY.md](SECURITY.md) for more on handling credentials safely.

## Run standalone

```bash
npm start
```

You should see `[ambee-mcp-server] running on stdio` on stderr. The process communicates over stdio and will wait for MCP messages — that's expected.

## Connect a client

The server speaks standard MCP over stdio, so it works with any compliant client. The command and environment variable are the same everywhere — only the config file format changes.

### Claude Code

```bash
claude mcp add --transport stdio ambee \
  -- node /absolute/path/to/ambee-mcp-server/src/index.js \
  --env AMBEE_API_KEY=your-ambee-api-key

claude mcp list   # confirm it shows as connected
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ambee": {
      "command": "node",
      "args": ["/absolute/path/to/ambee-mcp-server/src/index.js"],
      "env": {
        "AMBEE_API_KEY": "your-ambee-api-key"
      }
    }
  }
}
```

### Cursor

Add to `~/.cursor/mcp.json` (or the project-level `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "ambee": {
      "command": "node",
      "args": ["/absolute/path/to/ambee-mcp-server/src/index.js"],
      "env": {
        "AMBEE_API_KEY": "your-ambee-api-key"
      }
    }
  }
}
```

### VS Code (GitHub Copilot / MCP extension)

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "ambee": {
      "command": "node",
      "args": ["/absolute/path/to/ambee-mcp-server/src/index.js"],
      "env": {
        "AMBEE_API_KEY": "your-ambee-api-key"
      }
    }
  }
}
```

### Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "ambee": {
      "command": "node",
      "args": ["/absolute/path/to/ambee-mcp-server/src/index.js"],
      "env": {
        "AMBEE_API_KEY": "your-ambee-api-key"
      }
    }
  }
}
```

### Cline (VS Code extension)

Open Cline's MCP settings panel and add a new server with:
- **Command:** `node`
- **Args:** `/absolute/path/to/ambee-mcp-server/src/index.js`
- **Environment variable:** `AMBEE_API_KEY=your-ambee-api-key`

Or edit `cline_mcp_settings.json` directly using the same `command` / `args` / `env` shape as the examples above.

### Zed

Add to Zed's `settings.json` under `context_servers`:

```json
{
  "context_servers": {
    "ambee": {
      "command": {
        "path": "node",
        "args": ["/absolute/path/to/ambee-mcp-server/src/index.js"],
        "env": {
          "AMBEE_API_KEY": "your-ambee-api-key"
        }
      }
    }
  }
}
```

### Ollama

Ollama's native app doesn't speak MCP directly yet, but any Ollama model can call this server through an MCP-aware bridge or agent framework, since Ollama exposes an OpenAI-compatible API that MCP client libraries (such as [mcp-use](https://github.com/mcp-use/mcp-use) or LangChain's MCP adapters) can route tool calls through. A minimal example using `mcp-use` with a local Ollama model:

```python
from mcp_use import MCPAgent, MCPClient
from langchain_ollama import ChatOllama

client = MCPClient.from_dict({
    "mcpServers": {
        "ambee": {
            "command": "node",
            "args": ["/absolute/path/to/ambee-mcp-server/src/index.js"],
            "env": {"AMBEE_API_KEY": "your-ambee-api-key"},
        }
    }
})

llm = ChatOllama(model="llama3.1")
agent = MCPAgent(llm=llm, client=client)

result = agent.run("What's the air quality in Bengaluru right now?")
print(result)
```

### ChatGPT (developer mode / custom connectors)

ChatGPT's MCP connector support (developer mode, Team/Enterprise workspaces) expects a **remote** HTTP server rather than a local stdio process. To expose this server that way, run it behind an MCP-to-HTTP gateway (e.g. [`mcp-remote`](https://github.com/geelen/mcp-remote) or a small reverse proxy) and register the resulting URL as a custom connector in ChatGPT's settings.

### Any other MCP client

Every MCP client ultimately needs the same three things — a `command`, `args`, and an `env` block:

```json
{
  "command": "node",
  "args": ["/absolute/path/to/ambee-mcp-server/src/index.js"],
  "env": {
    "AMBEE_API_KEY": "your-ambee-api-key"
  }
}
```

Consult your client's docs for where this config block goes.

## Example prompts

- "How bad is the air in Los Angeles right now?"
- "When is PM2.5 lowest tomorrow so I can run outside?"
- "My kid has a grass allergy — is Saturday morning in Austin going to be rough for her?"
- "What's the UV index at 90210 right now, in metric units?"
- "Compare air quality between our Bengaluru and Austin offices."

## Support

- **Issues / bugs:** [GitHub Issues](https://github.com/getambee/ambee-mcp-server/issues)
- **API support:** [support.getambee.com](https://support.getambee.com)
- **API status:** [docs.ambeedata.com/api-status](https://docs.ambeedata.com/api-status)
- **Security reports:** see [SECURITY.md](SECURITY.md)

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose changes, our code style, and the PR process.

## Notes

- All tools are read-only; nothing here can modify your Ambee account or data.
- MCP calls draw from the same Ambee API quota/rate limits as REST calls.
- Only "latest" and "48-hour forecast" are exposed today. Ambee's `/v3` API also supports historical data and 120-hour forecasts — see [open issues](https://github.com/getambee/ambee-mcp-server/issues) or open a feature request.

## License

[MIT](LICENSE)
