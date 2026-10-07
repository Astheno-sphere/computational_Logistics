# PackZoo MCP Server

Compare parcel and letter delivery prices across 60+ carriers in 27 European
countries — live rates by weight, dimensions, origin, and destination.

PackZoo is a hosted, remote MCP server. Clients with native streamable-http
support can connect directly; this repo also ships a thin stdio proxy for
clients that only support local/stdio MCP servers.

## Connect directly (streamable-http)

```
https://packzoo.com/api/mcp
```

See [`server.json`](./server.json) for the full MCP registry manifest.

## Run locally (stdio proxy)

```bash
npx github:IAfanasov/packzoo-mcp
```

`src/index.js` is a small stdio&lt;-&gt;streamable-http bridge: it connects to
`https://packzoo.com/api/mcp`, forwards `tools/list` and `tools/call` over
stdio. Point your MCP client's config at this command for clients without
native remote-server support.

## Tool

### `compare_shipping_prices`

Compare shipping prices across carriers for a given package and route.

| Parameter     | Type   | Description                              |
|---------------|--------|-------------------------------------------|
| `from_country`| string | Origin country ISO code                   |
| `to_country`  | string | Destination country ISO code (ISO 3166-1) |
| `weight_kg`   | number | Package weight in kilograms               |
| `length_cm`   | number | Longest side, in centimetres               |
| `width_cm`    | number | Middle side, in centimetres                |
| `height_cm`   | number | Shortest side, in centimetres              |

## Links

- Website: https://packzoo.com
- REST API: https://packzoo.com/api/prices
- OpenAPI spec: https://packzoo.com/openapi.json
- Agent guide: https://packzoo.com/AGENTS.md
- llms.txt: https://packzoo.com/llms.txt
- MCP registry entry: `io.github.IAfanasov/packzoo`

## Coverage

Countries: AT, BE, BG, CY, CZ, DE, DK, EE, ES, FI, FR, GR, HR, HU, IE, IT, LT,
LU, LV, MT, NL, PL, PT, RO, SE, SI, SK.

## License

MIT — see [LICENSE](./LICENSE).
