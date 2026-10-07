# PostalDataPI MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/postaldatapi-mcp.svg)](https://pypi.org/project/postaldatapi-mcp/)

MCP (Model Context Protocol) server for [PostalDataPI](https://postaldatapi.com) — lets AI agents look up, validate, and search postal codes across **240+ countries and territories** with rich metadata: timezone, administrative regions, elevation, and coordinates.

## Tools

| Tool | Description |
|------|-------------|
| `lookup_postal_code` | Get city, state/region, and abbreviation for a postal code (US ZIP, UK postcode, German PLZ, etc.) |
| `validate_postal_code` | Check if a postal code exists in a country |
| `search_by_city` | Find all postal codes for a city |
| `get_postal_code_metadata` | Full metadata: coordinates, admin hierarchy, timezone, elevation, and more |

## Setup

### 1. Get an API Key

Sign up at [postaldatapi.com/register](https://postaldatapi.com/register) — 1,000 free queries, no credit card required.

### 2. Install

```bash
pip install postaldatapi-mcp
```

### 3. Configure with Claude Code

```bash
claude mcp add --transport stdio postaldatapi -- \
  env POSTALDATAPI_KEY=your_api_key_here postaldatapi-mcp
```

### 4. Configure with Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "postaldatapi": {
      "command": "postaldatapi-mcp",
      "env": {
        "POSTALDATAPI_KEY": "your_api_key_here"
      }
    }
  }
}
```

## Usage

Once configured, ask Claude naturally:

- "What city is ZIP code 90210?"
- "Look up UK postcode SW1A"
- "Is 10115 a valid German postal code?"
- "What are the postal codes for Beverly Hills, CA?"
- "Get the coordinates for postal code 100-0001 in Japan"

Claude will automatically use the PostalDataPI tools to answer.

## Supported Countries

240+ countries and territories including US, UK, Canada, Germany, France, Japan, Australia, Brazil, India, and many more. See the full list at [postaldatapi.com/countries](https://postaldatapi.com/countries).

## Rich Metadata

Beyond basic lookups, the `get_postal_code_metadata` tool returns up to 18 fields per postal code including:

- **Coordinates** (latitude, longitude)
- **Timezone** (e.g., `America/Mexico_City`, `Europe/Berlin`)
- **Administrative hierarchy** (state/province, county, municipality)
- **Elevation** (meters above sea level)
- **Place name** and country information

Example response for Mexico City 06000:

```json
{
  "postalCode": "06000",
  "country": "MX",
  "placeName": "Centro",
  "latitude": 19.4364,
  "longitude": -99.1553,
  "timezone": "America/Mexico_City",
  "adminLevel1": "Ciudad de México",
  "adminLevel2": "Cuauhtémoc",
  "elevation": 2239
}
```

## Links

- [PostalDataPI](https://postaldatapi.com)
- [API Reference](https://postaldatapi.com/reference)
- [Documentation](https://docs.postaldatapi.com)
- [Python SDK](https://pypi.org/project/postaldatapi/)
- [Node.js SDK](https://www.npmjs.com/package/postaldatapi)
