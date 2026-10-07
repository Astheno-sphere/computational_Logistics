# @sthan/mcp-server

MCP server for [sthan.io](https://sthan.io) — US address verification, parsing, autocomplete, geocoding, and IP geolocation.

Works with Claude Code, Cursor, VS Code, Windsurf, and any MCP-compatible client.

## Setup

### 1. Get an API key

Sign up at [sthan.io](https://sthan.io) (free tier, no credit card required). Create an API key from your [dashboard](https://sthan.io/dashboard).

### 2. One-click install

[![Add to Claude Desktop](https://img.shields.io/badge/Claude_Desktop-Download_extension-D97757?style=for-the-badge)](https://github.com/sthan-io/mcp-server/releases/latest/download/sthan.mcpb)
[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install-0098FF?style=for-the-badge&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=sthan&inputs=%5B%7B%22type%22%3A%22promptString%22%2C%22id%22%3A%22sthan_api_key%22%2C%22description%22%3A%22sthan.io%20API%20key%20%28free%20at%20https%3A//sthan.io%29%22%2C%22password%22%3Atrue%7D%5D&config=%7B%22type%22%3A%22stdio%22%2C%22command%22%3A%22npx%22%2C%22args%22%3A%5B%22-y%22%2C%22%40sthan/mcp-server%22%5D%2C%22env%22%3A%7B%22STHAN_API_KEY%22%3A%22%24%7Binput%3Asthan_api_key%7D%22%7D%7D)
[![Install in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-Install-24bfa5?style=for-the-badge&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=sthan&inputs=%5B%7B%22type%22%3A%22promptString%22%2C%22id%22%3A%22sthan_api_key%22%2C%22description%22%3A%22sthan.io%20API%20key%20%28free%20at%20https%3A//sthan.io%29%22%2C%22password%22%3Atrue%7D%5D&config=%7B%22type%22%3A%22stdio%22%2C%22command%22%3A%22npx%22%2C%22args%22%3A%5B%22-y%22%2C%22%40sthan/mcp-server%22%5D%2C%22env%22%3A%7B%22STHAN_API_KEY%22%3A%22%24%7Binput%3Asthan_api_key%7D%22%7D%7D&quality=insiders)
[![Add to Cursor](https://img.shields.io/badge/Cursor-Add_to_Cursor-000000?style=for-the-badge)](https://cursor.com/install-mcp?name=sthan&config=eyJjb21tYW5kIjoibnB4IiwiYXJncyI6WyIteSIsIkBzdGhhbi9tY3Atc2VydmVyIl0sImVudiI6eyJTVEhBTl9BUElfS0VZIjoieW91cl9rZXlfaGVyZSJ9fQ%3D%3D)

- **Claude Desktop**: download `sthan.mcpb` and double-click it. Claude asks for your API key and keeps it in your system keychain. Nothing else to install.
- **VS Code**: click the button. VS Code asks for your API key and stores it securely.
- **Cursor**: click the button, then replace `your_key_here` with your key in Cursor Settings > MCP.
- **Claude Code**: `claude mcp add sthan -e STHAN_API_KEY=your_key_here -- npx -y @sthan/mcp-server` (details below).

### 3. Or set it up manually

Replace `your_key_here` with your key. Every setup below downloads the latest `@sthan/mcp-server` from npm and calls the live API at `https://api.sthan.io`.

**Claude Code** (terminal):

```bash
claude mcp add sthan -e STHAN_API_KEY=your_key_here -- npx -y @sthan/mcp-server
```

On native Windows, wrap `npx` with `cmd /c`:

```powershell
claude mcp add sthan -e STHAN_API_KEY=your_key_here -- cmd /c npx -y @sthan/mcp-server
```

Add `--scope user` to use it in every project. Start `claude` and type `/mcp` to confirm `sthan` is connected.

**Claude Desktop**: edit `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`), then restart Claude Desktop:

```json
{
  "mcpServers": {
    "sthan": {
      "command": "npx",
      "args": ["-y", "@sthan/mcp-server"],
      "env": { "STHAN_API_KEY": "your_key_here" }
    }
  }
}
```

**Cursor**: the same JSON in `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project).

**Windsurf**: the same JSON in `~/.codeium/windsurf/mcp_config.json`.

**VS Code**: create `.vscode/mcp.json`. VS Code asks for the key once and stores it securely:

```json
{
  "inputs": [
    { "type": "promptString", "id": "sthan-api-key", "description": "sthan.io API key", "password": true }
  ],
  "servers": {
    "sthan": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@sthan/mcp-server"],
      "env": { "STHAN_API_KEY": "${input:sthan-api-key}" }
    }
  }
}
```

**Try it without an AI client** (opens the official MCP Inspector in your browser):

```bash
npx @modelcontextprotocol/inspector -e STHAN_API_KEY=your_key_here npx -y @sthan/mcp-server
```

Click **Connect**, then **Tools** > **List Tools**, pick a tool, and run it.

**Troubleshooting**

- Keep the `-y` in `npx -y`. Without it, `npx` waits for an "OK to install?" answer that an AI client cannot give, and the server never starts.
- On Windows, run the `claude mcp add ... cmd /c ...` command from PowerShell or Command Prompt. Git Bash rewrites `/c` to `C:/`, which saves a broken command that times out (fix: prefix it with `MSYS_NO_PATHCONV=1`).
- On Windows, if a client reports `spawn npx ENOENT`, use `"command": "cmd"` with `"args": ["/c", "npx", "-y", "@sthan/mcp-server"]`.
- Address verification and parsing can take up to about 2 minutes when a live postal lookup is needed. If your client gives up sooner, raise its tool timeout (Claude Code: set `MCP_TOOL_TIMEOUT=150000` before starting `claude`; MCP Inspector: raise **Request Timeout** in its Configuration panel).

## Tools

| Tool | Description |
|------|-------------|
| `sthan_verify_address` | Verify a US address for deliverability. Returns DPV confirmation, ZIP+4, carrier route. |
| `sthan_parse_address` | Parse freeform address text into structured components (street, city, state, zip, unit). |
| `sthan_autocomplete_address` | Get address suggestions from partial input. Sub-100ms response time. |
| `sthan_autocomplete_city` | Get US city suggestions from partial input. |
| `sthan_autocomplete_zipcode` | Get US ZIP code suggestions from partial input. |
| `sthan_geocode` | Convert a US address to latitude/longitude coordinates. |
| `sthan_reverse_geocode` | Convert coordinates to the nearest US street address. |
| `sthan_ip_geolocation` | Locate an IPv4 or IPv6 address: country to postal code, local time, flag and currency, plus the network behind it (ASN, ISP, proxy/hosting flags) and a confidence score. |

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `STHAN_API_KEY` | Yes | Your sthan.io API key (`sthan_test_*` or `sthan_live_*`) |
| `STHAN_API_URL` | No | Override base URL (default: `https://api.sthan.io`) |

## Examples

Once configured, just ask your AI assistant naturally:

- "Is 123 Main St, New York, NY 10001 a real address?"
- "Parse this address: apt 2b 500 broadway new york ny"
- "What are the coordinates for the White House?"
- "What address is at 40.7128, -74.0060?"
- "Where is IP 8.8.8.8 located?"

## Links

- [API docs](https://sthan.io/docs)
- [Pricing](https://sthan.io/pricing/united-states)
- [OpenAPI spec](https://api.sthan.io/openapi.json)
- [AI reference](https://api.sthan.io/llms-full.txt)

## License

MIT
