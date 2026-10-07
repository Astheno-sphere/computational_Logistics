# bamwor-mcp-server

MCP Server for world geographic data — 261 countries, 13.4M cities. Connect AI agents to real country and city data.

Works with **Claude Desktop**, **Cursor**, **Windsurf**, and any MCP-compatible client.

## Quick Start

```bash
npx bamwor-mcp-server
```

Or install globally:

```bash
npm install -g bamwor-mcp-server
bamwor-mcp-server
```

## Configuration

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bamwor-world-data": {
      "command": "npx",
      "args": ["-y", "bamwor-mcp-server"],
      "env": {
        "BAMWOR_API_KEY": "your_api_key"
      }
    }
  }
}
```

### Cursor / Windsurf

Add to your MCP settings:

```json
{
  "bamwor-world-data": {
    "command": "npx",
    "args": ["-y", "bamwor-mcp-server"],
    "env": {
      "BAMWOR_API_KEY": "your_api_key"
    }
  }
}
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BAMWOR_API_KEY` | No | (anonymous) | API key for full access. Get one free at [bamwor.com/en/developers/quickstart](https://bamwor.com/en/developers/quickstart) |
| `BAMWOR_API_URL` | No | `https://bamwor.com/api/v1` | API base URL override |
| `BAMWOR_REQUEST_TIMEOUT` | No | `15000` | Request timeout in ms |

## Available Tools (8)

### get_country

Get detailed data about a country by name, slug, or ISO code. Returns population, area, capital, region, coordinates, and 20+ statistics.

```
Input: { "query": "Japan" }
```

### search_countries

Search for countries by name or keyword. Returns matching countries with basic data.

```
Input: { "query": "south", "limit": 10 }
```

### search_cities

Search for cities worldwide by name from a database of 13.4M cities.

```
Input: { "query": "Tokyo", "limit": 5 }
```

### list_cities_by_country

List cities in a specific country, sorted by population or name. Supports minimum population filter.

```
Input: { "country": "brazil", "min_population": 1000000, "limit": 10 }
```

### compare_countries

Compare two countries side by side across all available metrics: population, area, GDP, HDI, life expectancy, and more.

```
Input: { "country_a": "France", "country_b": "Germany" }
```

### get_rankings

Get country rankings by metric. Available metrics: population, area, gdp, hdi, life-expectancy, and 9 Bamwor proprietary indices (ibeu, ibcp, ibda, ibcx, ibee, ibfm, ibdi, ibed, ibsa). Omit metric to list all available.

```
Input: { "metric": "population", "limit": 10, "countries_only": true }
```

### get_city

Get detailed information about a specific city by its GeoNames ID. Returns coordinates, population, elevation, timezone, and province.

```
Input: { "city_id": 1850147 }
```

### get_nearby_cities

Find cities near a specific city using PostGIS radius search. Returns nearby cities with distance in km.

```
Input: { "city_id": 1850147, "radius": 50, "limit": 10 }
```

## Data Coverage

- **261 countries and territories** with 20+ statistics each
- **13.4 million cities** with coordinates, population, elevation, timezone
- **9 proprietary indices** (IBEU, IBCP, IBDA, IBCX, IBEE, IBFM, IBDI, IBED, IBSA)
- **Rankings** by any metric
- **Country comparisons** — 67,860 combinations
- **4 languages** — English, Spanish, Portuguese, Italian

Data sourced from CIA World Factbook, GeoNames, UNDP, and World Bank.

## Links

- [API Documentation](https://bamwor.com/en/developers/docs)
- [Get Free API Key](https://bamwor.com/en/developers/quickstart)
- [API Playground](https://bamwor.com/en/developers/playground)
- [Pricing](https://bamwor.com/en/developers/pricing)
- [GitHub](https://github.com/bamwor-dev/bamwor-mcp-server)

## License

MIT
