#!/usr/bin/env node
// The shebang is what makes the `bin` entry runnable via npx or a global
// install. TypeScript preserves a leading shebang into the emitted dist file.
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import {
  fetchAduLeads,
  fetchMarketSignals,
  fetchPermits,
  fetchPropertyIntelligence,
  fetchRedevelopmentLeads,
  fetchSb9Inventory,
} from "./api.js";

const server = new Server(
  {
    name: "addressintel-mcp-server",
    version: "1.1.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

/**
 * One entry per tool. `args` is the zod schema used to validate the incoming
 * call and `inputSchema` is the JSON Schema advertised to the client. They are
 * declared side by side so the pair cannot drift, which is easy to do when each
 * tool spells its shape out twice in two separate blocks.
 */
interface ToolDef<T extends z.ZodTypeAny> {
  name: string;
  description: string;
  inputSchema: {
    type: "object";
    properties: Record<string, { type: string; description: string; enum?: string[] }>;
    required?: string[];
  };
  args: T;
  run: (args: z.infer<T>) => Promise<unknown>;
}

function tool<T extends z.ZodTypeAny>(def: ToolDef<T>): ToolDef<z.ZodTypeAny> {
  return def as ToolDef<z.ZodTypeAny>;
}

// Shared paging arg. Every list endpoint clamps this to the key's tier ceiling
// (5 rows on the demo key, 25 free, 500 pro), so an over-large ask degrades
// rather than erroring.
const limitProp = {
  type: "number",
  description: "Max rows to return. Clamped to your API key's tier ceiling.",
};

const TOOLS: ToolDef<z.ZodTypeAny>[] = [
  tool({
    name: "search_permits",
    description:
      "Search issued building permits across the SF Peninsula and adjacent Silicon Valley cities. Filter by city, keyword (address, project type, scope description, contractor, architect or permit number) and minimum valuation. Use this to find what construction has actually been permitted at an address or in a city.",
    inputSchema: {
      type: "object",
      properties: {
        city: { type: "string", description: "City name, e.g. 'Menlo Park'. Partial matches allowed." },
        q: {
          type: "string",
          description:
            "Keyword matched against address, project type, scope description, contractor, architect and permit number, e.g. 'demolition' or '123 Main St'.",
        },
        minValuation: { type: "number", description: "Only permits valued at or above this dollar amount." },
        limit: limitProp,
        offset: { type: "number", description: "Row offset for paging." },
      },
    },
    args: z.object({
      city: z.string().optional(),
      q: z.string().optional(),
      minValuation: z.number().optional(),
      limit: z.number().optional(),
      offset: z.number().optional(),
    }),
    run: (args) => fetchPermits(args),
  }),

  tool({
    name: "list_sb9_inventory",
    description:
      "List active listings that are eligible for an SB 9 lot split or duplex conversion, with the per-parcel block reasons where they are not. California-only; this is a parcel-level buildability read, not a generic lead list.",
    inputSchema: {
      type: "object",
      properties: {
        status: {
          type: "string",
          description: "Filter by SB 9 status. Defaults to any non-blocked parcel.",
          enum: ["eligible", "likely", "any"],
        },
        minUnits: { type: "number", description: "Only parcels supporting at least this many SB 9 units." },
        excludeBlockers: {
          type: "boolean",
          description: "Drop parcels carrying any development blocker.",
        },
        limit: limitProp,
      },
    },
    args: z.object({
      status: z.enum(["eligible", "likely", "any"]).optional(),
      minUnits: z.number().optional(),
      excludeBlockers: z.boolean().optional(),
      limit: z.number().optional(),
    }),
    run: (args) => fetchSb9Inventory(args),
  }),

  tool({
    name: "list_adu_leads",
    description:
      "List parcels ranked by ADU (accessory dwelling unit) feasibility, including estimated max units, buildable square footage and the lot geometry behind the score.",
    inputSchema: {
      type: "object",
      properties: {
        minScore: { type: "number", description: "Minimum ADU feasibility score, 0-100. Defaults to 60." },
        excludeBlockers: { type: "boolean", description: "Drop parcels carrying any development blocker." },
        limit: limitProp,
      },
    },
    args: z.object({
      minScore: z.number().optional(),
      excludeBlockers: z.boolean().optional(),
      limit: z.number().optional(),
    }),
    run: (args) => fetchAduLeads(args),
  }),

  tool({
    name: "list_redevelopment_leads",
    description:
      "List underbuilt parcels: small, older homes using a low share of their allowable building envelope on sizable lots. Ranked by redevelopment score, with the FAR headroom that produced it.",
    inputSchema: {
      type: "object",
      properties: {
        minScore: { type: "number", description: "Minimum redevelopment score, 0-100. Defaults to 60." },
        class: {
          type: "string",
          description: "Narrow to scrape-and-rebuild candidates or expansion candidates.",
          enum: ["teardown_candidate", "expansion"],
        },
        excludeBlockers: { type: "boolean", description: "Drop parcels carrying any development blocker." },
        limit: limitProp,
      },
    },
    args: z.object({
      minScore: z.number().optional(),
      class: z.enum(["teardown_candidate", "expansion"]).optional(),
      excludeBlockers: z.boolean().optional(),
      limit: z.number().optional(),
    }),
    run: (args) => fetchRedevelopmentLeads(args),
  }),

  tool({
    name: "list_market_signals",
    description:
      "Search for high-signal real estate investment opportunities (teardowns, flips). Use this to find properties before diving into specific details. Each result carries proformaROI, a net teardown ROI computed by arithmetic rather than by a model, with a proforma object holding its inputs and assumptions ($400/sqft build, 5% cost of sale, build sized to the zoning envelope). Quote those assumptions alongside the number. null means not modellable, with unmodellableReason naming the missing input: treat it as unknown, never as zero. Negatives are normal here; most of this market does not pencil.",
    inputSchema: {
      type: "object",
      properties: {
        market: { type: "string", description: "Filter by market (e.g. 'sf-peninsula' or 'nantucket')" },
        city: { type: "string", description: "Filter by city name (e.g. 'Atherton')" },
        address: { type: "string", description: "Search for a specific address" },
        limit: limitProp,
      },
    },
    args: z.object({
      market: z.string().optional(),
      city: z.string().optional(),
      address: z.string().optional(),
      limit: z.number().optional(),
    }),
    run: (args) => fetchMarketSignals(args),
  }),

  tool({
    name: "get_property_intelligence",
    description:
      "Get detailed AI intelligence for a specific property. Takes an id from list_market_signals. Returns teardown and flippability scores, a market heat index, an AI briefing, comparable-sale counts with an average price per sqft, and parcel enrichment (zoning, lot size, development class). Those scores rank candidates; none of them is a return. This endpoint carries no ROI figure at all: for that, read proformaROI from list_market_signals, which is arithmetic rather than a model estimate.",
    inputSchema: {
      type: "object",
      properties: {
        id: { type: "string", description: "The unique identifier (ID) of the property to analyze" },
      },
      required: ["id"],
    },
    args: z.object({ id: z.string() }),
    run: async (args) => {
      const data = await fetchPropertyIntelligence(args.id);
      // A miss is a normal answer here, not a failure: the id may simply sit
      // outside our coverage. Say so in words the model can act on.
      return data ?? { found: false, message: `No property found with ID: ${args.id}` };
    },
  }),
];

const BY_NAME = new Map(TOOLS.map((t) => [t.name, t]));

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS.map(({ name, description, inputSchema }) => ({ name, description, inputSchema })),
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: rawArgs } = request.params;
  try {
    const def = BY_NAME.get(name);
    if (!def) throw new Error(`Unknown tool: ${name}`);

    const data = await def.run(def.args.parse(rawArgs ?? {}));
    return {
      content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      content: [{ type: "text", text: `Error: ${message}` }],
      isError: true,
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("AddressIntel MCP Server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error running MCP server:", error);
  process.exit(1);
});
