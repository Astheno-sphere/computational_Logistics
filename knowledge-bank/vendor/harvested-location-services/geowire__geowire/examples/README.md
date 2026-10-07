# GeoWire examples

**Connect an MCP client**

| Example | What it shows |
|---|---|
| [`mcp-clients.md`](./mcp-clients.md) | Configs for Claude Desktop/Code, Cursor, Cline, VS Code, Windsurf, HTTP |
| [`claude-desktop.json`](./claude-desktop.json) | Minimal Claude Desktop stdio config |
| [`cursor.json`](./cursor.json) | Minimal Cursor stdio config |

**Call it from code**

| Example | What it shows |
|---|---|
| [`typescript-sdk.md`](./typescript-sdk.md) | Embed `@geowirehq/core` in-process (no server) |
| [`langchain.md`](./langchain.md) | Python / LangChain agent (REST) |
| [`vercel-ai-sdk.md`](./vercel-ai-sdk.md) | Vercel AI SDK (TypeScript) |
| [`llm-tool-use.md`](./llm-tool-use.md) | Raw OpenAI / Anthropic function calling |

**Configure & extend**

| Example | What it shows |
|---|---|
| [`geowire.config.yaml`](./geowire.config.yaml) | Full config: providers, routing, budget, cache |
| [`customer-csv/`](./customer-csv/) | Your own places as a provider (CSV) |

For end-to-end walkthroughs (merge + dedup, budgets, provenance, country
routing), see [`../docs/recipes.md`](../docs/recipes.md).

All examples work with **zero API keys** (OpenStreetMap by default). Add
`GOOGLE_MAPS_API_KEY` to enable Google.
