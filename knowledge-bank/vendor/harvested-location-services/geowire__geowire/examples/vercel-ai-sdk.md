# GeoWire from the Vercel AI SDK

## Option A — MCP (recommended)

GeoWire's tools load directly via MCP. Start the HTTP server (`npx @geowirehq/cli`) and
connect the AI SDK's MCP client:

```ts
import { experimental_createMCPClient as createMCPClient } from "ai";
import { generateText } from "ai";
import { openai } from "@ai-sdk/openai";

const mcp = await createMCPClient({
  transport: { type: "sse", url: "http://localhost:4980/mcp" },
});
const tools = await mcp.tools(); // search_places, get_place, geocode_address, ...

const { text } = await generateText({
  model: openai("gpt-4o"),
  tools,
  prompt: "Find a 24-hour pharmacy near District 1, Ho Chi Minh City.",
});

await mcp.close();
```

## Option B — a hand-written tool over REST

```ts
import { tool, generateText } from "ai";
import { openai } from "@ai-sdk/openai";
import { z } from "zod";

const searchPlaces = tool({
  description: "Search for real-world places by natural-language query, optionally near a coordinate.",
  parameters: z.object({
    query: z.string(),
    near: z.object({ latitude: z.number(), longitude: z.number() }).optional(),
  }),
  execute: async (args) => {
    const res = await fetch("http://localhost:4980/v1/places/search", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(args),
    });
    return res.json();
  },
});

const { text } = await generateText({
  model: openai("gpt-4o"),
  tools: { searchPlaces },
  prompt: "Find coffee near downtown San Francisco.",
});
```
