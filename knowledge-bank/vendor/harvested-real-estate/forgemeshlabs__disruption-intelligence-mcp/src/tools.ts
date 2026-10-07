import { DisruptionApiClient, type ApiRequestResult } from "./client.js";

type JsonObject = Record<string, unknown>;

export type McpToolAnnotations = {
  readOnlyHint: boolean;
  destructiveHint: boolean;
  idempotentHint: boolean;
  openWorldHint: boolean;
};

export type McpTool = {
  name: string;
  description: string;
  inputSchema: JsonObject;
  annotations: McpToolAnnotations;
};

const READ_ONLY_EXTERNAL: McpToolAnnotations = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: false,
  openWorldHint: true,
};

export const tools: McpTool[] = [
  {
    name: "get_api_status",
    annotations: READ_ONLY_EXTERNAL,
    description: "Check the hosted Disruption Intelligence API health endpoint. Free.",
    inputSchema: {
      type: "object",
      properties: {},
      additionalProperties: false
    }
  },
  {
    name: "get_discovery_metadata",
    annotations: READ_ONLY_EXTERNAL,
    description: "Fetch free discovery metadata from index.json, llms.txt, openapi.json, and x402 well-known metadata. Free.",
    inputSchema: {
      type: "object",
      properties: {},
      additionalProperties: false
    }
  },
  {
    name: "inspect_x402_challenge",
    annotations: READ_ONLY_EXTERNAL,
    description: "Make an unpaid request to a paid endpoint and return the structured x402 payment challenge. Does not settle payment.",
    inputSchema: {
      type: "object",
      properties: {
        endpoint: {
          type: "string",
          description: "Paid endpoint path to inspect. Defaults to /territory/77001/disruption?radius=50."
        }
      },
      additionalProperties: false
    }
  },
  {
    name: "analyze_territory_disruption",
    annotations: READ_ONLY_EXTERNAL,
    description: "Thin wrapper for GET /territory/:zip/disruption?radius=. Paid endpoint; returns x402 challenge in default non-settling mode.",
    inputSchema: {
      type: "object",
      required: ["zip"],
      properties: {
        zip: {
          type: "string",
          description: "US ZIP code to analyze."
        },
        radius: {
          type: "number",
          description: "Search radius in miles. Defaults to 50."
        }
      },
      additionalProperties: false
    }
  },
  {
    name: "search_company_context",
    annotations: READ_ONLY_EXTERNAL,
    description: "Thin wrapper for GET /companies/search?q=. Paid endpoint; returns x402 challenge in default non-settling mode.",
    inputSchema: {
      type: "object",
      required: ["q"],
      properties: {
        q: {
          type: "string",
          description: "Company search query."
        }
      },
      additionalProperties: false
    }
  },
  {
    name: "get_company_risk_summary",
    annotations: READ_ONLY_EXTERNAL,
    description: "Thin wrapper for GET /companies/:id/intelligence. Paid endpoint; returns x402 challenge in default non-settling mode.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: {
        id: {
          type: "string",
          description: "Company identifier accepted by the hosted API."
        }
      },
      additionalProperties: false
    }
  },

  {
    name: "get_event_severity",
    annotations: READ_ONLY_EXTERNAL,
    description: "Thin wrapper for GET /events/:id/severity. Paid endpoint; enriched paid responses include industry_classification with method, confidence, and coverage_note. Returns x402 challenge in default non-settling mode.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: {
        id: {
          type: "string",
          description: "Event identifier accepted by the hosted API."
        }
      },
      additionalProperties: false
    }
  },
  {
    name: "get_event_company_intel",
    annotations: READ_ONLY_EXTERNAL,
    description: "Thin wrapper for GET /events/:id/company-intel. Paid endpoint; enriched paid responses include event industry_classification with method, confidence, and coverage_note. Returns x402 challenge in default non-settling mode.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: {
        id: {
          type: "string",
          description: "Event identifier accepted by the hosted API."
        }
      },
      additionalProperties: false
    }
  },
  {
    name: "get_event_timeline",
    annotations: READ_ONLY_EXTERNAL,
    description: "Thin wrapper for GET /events/:id/timeline. Paid endpoint; returns x402 challenge in default non-settling mode.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: {
        id: {
          type: "string",
          description: "Event identifier accepted by the hosted API."
        }
      },
      additionalProperties: false
    }
  },
  {
    name: "search_gold_inventory",
    annotations: READ_ONLY_EXTERNAL,
    description: "Compatibility tool for free inventory-only Ripple Signal search. Returns counts and unlock pricing without revealing signal details.",
    inputSchema: {
      type: "object",
      properties: {
        q: {
          type: "string",
          description: "Optional commercial angle, company, region, or industry search query."
        }
      },
      additionalProperties: false
    }
  },
  {
    name: "get_ripple_index",
    annotations: READ_ONLY_EXTERNAL,
    description: "Thin wrapper for GET /ripple/index. Paid endpoint currently priced at $0.01; returns location-only Ripple index cards with signal IDs, bands, and unlock URLs while withholding companies, employee counts, commercial angles, and impact paths.",
    inputSchema: {
      type: "object",
      properties: {
        q: {
          type: "string",
          description: "Optional region, state, or broad signal search query."
        },
        scope: {
          type: "string",
          enum: ["all", "gold", "watchlist"],
          description: "Index scope. Defaults to all on the hosted API."
        },
        limit: {
          type: "number",
          description: "Maximum index cards to return. Hosted API caps this at 25."
        }
      },
      additionalProperties: false
    }
  },
  {
    name: "get_gold_signals",
    annotations: READ_ONLY_EXTERNAL,
    description: "Compatibility tool for GET /ripple/signals. Paid endpoint currently priced at $0.10; returns Ripple Signals and Ripple Path inventory, challenge-first by default.",
    inputSchema: {
      type: "object",
      properties: {
        q: {
          type: "string",
          description: "Optional commercial angle, company, region, or industry search query."
        },
        limit: {
          type: "number",
          description: "Maximum signals to return. Hosted API caps this at 10."
        },
        state: {
          type: "string",
          enum: ["gold", "watchlist"],
          description: "Signal state to request. Defaults to gold."
        }
      },
      additionalProperties: false
    }
  },
  {
    name: "get_gold_brief",
    annotations: READ_ONLY_EXTERNAL,
    description: "Compatibility tool for GET /ripple/brief. Paid endpoint currently priced at $0.25; returns a Disruption Intelligence Ripple Report, challenge-first by default.",
    inputSchema: {
      type: "object",
      properties: {
        q: {
          type: "string",
          description: "Optional commercial angle, company, region, or industry search query."
        },
        scope: {
          type: "string",
          enum: ["all", "gold", "watchlist"],
          description: "Brief scope. Defaults to all on the hosted API."
        },
        limit: {
          type: "number",
          description: "Maximum delivered signals to include. Hosted API caps this at 10."
        }
      },
      additionalProperties: false
    }
  },
  {
    name: "get_gold_sector_impacts",
    annotations: READ_ONLY_EXTERNAL,
    description: "Compatibility tool for GET /ripple/signals/:id/sector-impacts. Paid endpoint currently priced at $0.15; returns Ripple Paths with deep operational spend and downstream sector impacts for one signal, challenge-first by default.",
    inputSchema: {
      type: "object",
      required: ["id"],
      properties: {
        id: {
          type: "string",
          description: "Ripple signal UUID."
        }
      },
      additionalProperties: false
    }
  }
];

export async function callTool(name: string, args: JsonObject = {}, client = new DisruptionApiClient()): Promise<unknown> {
  switch (name) {
    case "get_api_status":
      return client.get("/health");
    case "get_discovery_metadata":
      return client.getDiscoveryMetadata();
    case "inspect_x402_challenge":
      return inspectChallenge(client, stringArg(args, "endpoint") ?? "/territory/77001/disruption?radius=50");
    case "analyze_territory_disruption": {
      const zip = requiredStringArg(args, "zip");
      const radius = numberArg(args, "radius") ?? 50;
      return client.get(`/territory/${encodeURIComponent(zip)}/disruption?radius=${encodeURIComponent(String(radius))}`);
    }
    case "search_company_context": {
      const q = requiredStringArg(args, "q");
      return client.get(`/companies/search?q=${encodeURIComponent(q)}`);
    }
    case "get_company_risk_summary": {
      const id = requiredStringArg(args, "id");
      return client.get(`/companies/${encodeURIComponent(id)}/intelligence`);
    }
    case "get_event_severity": {
      const id = requiredStringArg(args, "id");
      return client.get(`/events/${encodeURIComponent(id)}/severity`);
    }
    case "get_event_company_intel": {
      const id = requiredStringArg(args, "id");
      return client.get(`/events/${encodeURIComponent(id)}/company-intel`);
    }
    case "get_event_timeline": {
      const id = requiredStringArg(args, "id");
      return client.get(`/events/${encodeURIComponent(id)}/timeline`);
    }
    case "search_gold_inventory": {
      return client.get(withQuery("/ripple/search", { q: stringArg(args, "q") }));
    }
    case "get_ripple_index": {
      return client.get(withQuery("/ripple/index", {
        q: stringArg(args, "q"),
        scope: enumArg(args, "scope", ["all", "gold", "watchlist"]),
        limit: numberArg(args, "limit")
      }));
    }
    case "get_gold_signals": {
      return client.get(withQuery("/ripple/signals", {
        q: stringArg(args, "q"),
        limit: numberArg(args, "limit"),
        state: enumArg(args, "state", ["gold", "watchlist"])
      }));
    }
    case "get_gold_brief": {
      return client.get(withQuery("/ripple/brief", {
        q: stringArg(args, "q"),
        scope: enumArg(args, "scope", ["all", "gold", "watchlist"]),
        limit: numberArg(args, "limit")
      }));
    }
    case "get_gold_sector_impacts": {
      const id = requiredStringArg(args, "id");
      return client.get(`/ripple/signals/${encodeURIComponent(id)}/sector-impacts`);
    }
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

async function inspectChallenge(client: DisruptionApiClient, endpoint: string): Promise<ApiRequestResult> {
  const result = await client.get(endpoint);
  if (result.ok || result.status === 402) {
    return result;
  }

  return {
    ok: false,
    status: result.status,
    url: result.url,
    paymentRequired: false,
    error: {
      message: "Endpoint did not return an x402 payment challenge.",
      upstream: result.error
    }
  };
}

function requiredStringArg(args: JsonObject, key: string): string {
  const value = args[key];
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`Missing required string argument: ${key}`);
  }
  return value;
}

function stringArg(args: JsonObject, key: string): string | undefined {
  const value = args[key];
  if (value === undefined) {
    return undefined;
  }
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`Expected ${key} to be a non-empty string`);
  }
  return value;
}

function numberArg(args: JsonObject, key: string): number | undefined {
  const value = args[key];
  if (value === undefined) {
    return undefined;
  }
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`Expected ${key} to be a finite number`);
  }
  return value;
}

function enumArg<T extends string>(args: JsonObject, key: string, allowed: readonly T[]): T | undefined {
  const value = args[key];
  if (value === undefined) {
    return undefined;
  }
  if (typeof value !== "string" || !allowed.includes(value as T)) {
    throw new Error(`Expected ${key} to be one of: ${allowed.join(", ")}`);
  }
  return value as T;
}

function withQuery(path: string, params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      query.set(key, String(value));
    }
  }
  const encoded = query.toString();
  return encoded ? `${path}?${encoded}` : path;
}
