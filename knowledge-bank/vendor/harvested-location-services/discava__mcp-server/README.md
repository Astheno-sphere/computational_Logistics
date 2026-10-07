# Discava MCP Server

MCP server for AI agents to search local businesses worldwide via the Discava API.

[![discava – Business Directory for AI MCP server](https://glama.ai/mcp/servers/discava/mcp-server/badges/card.svg)](https://glama.ai/mcp/servers/discava/mcp-server)

## Setup

### Claude Desktop

Add to your Claude Desktop config (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "discava": {
      "command": "npx",
      "args": ["tsx", "/path/to/discava/mcp/server.ts"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add discava npx tsx /path/to/discava/mcp/server.ts
```

## Tools

| Tool | Description |
|------|-------------|
| `search_businesses` | Search for businesses by query, city, country |
| `get_business` | Get full details for a business by ID |
| `send_feedback` | Report data quality issues |
| `get_rankings` | Top businesses by demand score |
| `suggest` | Autocomplete for cities and categories |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCAVA_API_URL` | `https://discava.ai/api/v1` | API base URL |