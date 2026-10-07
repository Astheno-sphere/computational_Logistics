#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { SthanClient, SthanApiError } from "@sthan/core";
import { z } from "zod";

const MISSING_KEY_MESSAGE =
  "STHAN_API_KEY environment variable is not set. " +
  "Get a free key at https://sthan.io/dashboard, then set STHAN_API_KEY in your MCP client config.";

function getClient(): SthanClient {
  const apiKey = process.env.STHAN_API_KEY;
  if (!apiKey) {
    throw new Error(MISSING_KEY_MESSAGE);
  }
  return new SthanClient({
    apiKey,
    baseUrl: process.env.STHAN_API_URL,
  });
}

// Every tool is a read-only lookup against the sthan.io API: no state is
// changed, repeating a call with the same input returns the same result, and
// it reaches an external service (the open world of US addresses).
const READ_ONLY_HINTS = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
} as const;

const server = new McpServer({
  name: "sthan",
  version: "0.1.7",
});

// --- Tool 1: Verify US Address ---

server.registerTool(
  "sthan_verify_address",
  {
    title: "Verify US Address",
    description:
      "Verify whether a US street address is real and deliverable. Returns the standardized address, ZIP+4, county, a deliverability status, and the dpvConfirmation code (Y = deliverable; N = not found or undeliverable; S = address found but the apartment/unit is missing or unconfirmed; blank = unknown). " +
      "Use to confirm a US mailing address, clean address data, or check an address before shipping. " +
      "Do not use for non-US addresses, to get map coordinates (use sthan_geocode), or to only split an address into fields without checking it (use sthan_parse_address). " +
      "Read-only with no side effects. Requires a sthan.io API key in STHAN_API_KEY; each call counts toward your plan's rate limit (a free tier is available). On failure it returns an error message, for example an invalid API key, an exceeded rate limit, or an address that could not be found.",
    inputSchema: {
      address: z
        .string()
        .describe(
          "Full or partial US address in any format. Examples: '123 Main St, New York, NY 10001', '123 main st nyc', '1600 Pennsylvania Ave Washington DC'"
        ),
    },
    annotations: READ_ONLY_HINTS,
  },
  async ({ address }) => {
    try {
      const response = await getClient().verifyAddress(address);
      return {
        content: [{ type: "text", text: JSON.stringify(response.Result, null, 2) }],
      };
    } catch (e) {
      return errorResult(e);
    }
  }
);

// --- Tool 2: Parse US Address ---

server.registerTool(
  "sthan_parse_address",
  {
    title: "Parse US Address",
    description:
      "Break a freeform US address string into structured components: address number, street name, pre/post directionals, street type, unit type and number, city, state, ZIP, and ZIP+4. " +
      "Use when you have messy or unstructured US address text and need the individual fields. " +
      "This parses and standardizes only; it does not confirm the address is deliverable (use sthan_verify_address) and does not return coordinates (use sthan_geocode). " +
      "Read-only with no side effects. Requires a sthan.io API key in STHAN_API_KEY; each call counts toward your plan's rate limit (a free tier is available). On failure it returns an error message, for example an invalid API key or an exceeded rate limit.",
    inputSchema: {
      address: z
        .string()
        .describe(
          "Raw address text to parse. Freeform input, abbreviations OK. Example: 'apt 2b 500 broadway new york ny'"
        ),
    },
    annotations: READ_ONLY_HINTS,
  },
  async ({ address }) => {
    try {
      const response = await getClient().parseAddress(address);
      return {
        content: [{ type: "text", text: JSON.stringify(response.Result, null, 2) }],
      };
    } catch (e) {
      return errorResult(e);
    }
  }
);

// --- Tool 3: Autocomplete US Address ---

server.registerTool(
  "sthan_autocomplete_address",
  {
    title: "Autocomplete US Address",
    description:
      "Return a list of complete US street-address suggestions for partial input, intended for type-ahead / autocomplete fields. " +
      "Use while a user is typing an address and you want to offer full matches. " +
      "For city-only suggestions use sthan_autocomplete_city; for ZIP-only suggestions use sthan_autocomplete_zipcode; to validate a finished address use sthan_verify_address. " +
      "Read-only with no side effects. Requires a sthan.io API key in STHAN_API_KEY; each call counts toward your plan's rate limit (a free tier is available). On failure it returns an error message.",
    inputSchema: {
      text: z
        .string()
        .describe("Partial address text (3+ characters recommended). Example: '123 Main'"),
    },
    annotations: READ_ONLY_HINTS,
  },
  async ({ text }) => {
    try {
      const response = await getClient().autocompleteAddress(text);
      return {
        content: [{ type: "text", text: JSON.stringify(response.Result, null, 2) }],
      };
    } catch (e) {
      return errorResult(e);
    }
  }
);

// --- Tool 4: Autocomplete US City ---

server.registerTool(
  "sthan_autocomplete_city",
  {
    title: "Autocomplete US City",
    description:
      "Return a list of US city suggestions (with state) for partial input. " +
      "Use for city-field type-ahead, or to resolve a partial city name to its full name and state. " +
      "For full street-address suggestions use sthan_autocomplete_address; for ZIP codes use sthan_autocomplete_zipcode. " +
      "Read-only with no side effects. Requires a sthan.io API key in STHAN_API_KEY; each call counts toward your plan's rate limit (a free tier is available). On failure it returns an error message.",
    inputSchema: {
      text: z.string().describe("Partial city name. Example: 'San Fr'"),
      display_type: z
        .number()
        .int()
        .min(0)
        .max(1)
        .default(0)
        .describe(
          "0 = City, StateCode (e.g. 'San Francisco, CA'). 1 = City, State (e.g. 'San Francisco, California')"
        ),
    },
    annotations: READ_ONLY_HINTS,
  },
  async ({ text, display_type }) => {
    try {
      const response = await getClient().autocompleteCity(text, display_type);
      return {
        content: [{ type: "text", text: JSON.stringify(response.Result, null, 2) }],
      };
    } catch (e) {
      return errorResult(e);
    }
  }
);

// --- Tool 5: Autocomplete US ZIP Code ---

server.registerTool(
  "sthan_autocomplete_zipcode",
  {
    title: "Autocomplete US ZIP Code",
    description:
      "Return a list of US ZIP code suggestions for partial input, each with state (and optionally ZIP+4). " +
      "Use for ZIP-field type-ahead or to expand a partial ZIP. " +
      "For city suggestions use sthan_autocomplete_city; for full addresses use sthan_autocomplete_address. " +
      "Read-only with no side effects. Requires a sthan.io API key in STHAN_API_KEY; each call counts toward your plan's rate limit (a free tier is available). On failure it returns an error message.",
    inputSchema: {
      text: z.string().describe("Partial ZIP code. Example: '9021'"),
      display_type: z
        .number()
        .int()
        .min(0)
        .max(3)
        .default(0)
        .describe(
          "0 = Zip,StateCode. 1 = Zip,State. 2 = Zip-Zip4,StateCode. 3 = Zip-Zip4,State"
        ),
    },
    annotations: READ_ONLY_HINTS,
  },
  async ({ text, display_type }) => {
    try {
      const response = await getClient().autocompleteZipCode(text, display_type);
      return {
        content: [{ type: "text", text: JSON.stringify(response.Result, null, 2) }],
      };
    } catch (e) {
      return errorResult(e);
    }
  }
);

// --- Tool 6: Forward Geocode US Address ---

server.registerTool(
  "sthan_geocode",
  {
    title: "Geocode US Address",
    description:
      "Convert a US address to latitude/longitude coordinates. Returns the coordinates, a formatted address, an accuracy type (rooftop, interpolated, centroid, or approximate), and a confidence score. " +
      "Use when you need map coordinates for an address. " +
      "To go the other way (coordinates to address) use sthan_reverse_geocode; to check deliverability rather than location use sthan_verify_address. " +
      "Read-only with no side effects. Requires a sthan.io API key in STHAN_API_KEY; each call counts toward your plan's rate limit (a free tier is available). On failure it returns an error message, for example an address that could not be located.",
    inputSchema: {
      address: z
        .string()
        .describe(
          "US address to geocode (freeform text). Example: '1600 Pennsylvania Ave, Washington DC'"
        ),
    },
    annotations: READ_ONLY_HINTS,
  },
  async ({ address }) => {
    try {
      const response = await getClient().geocodeAddress(address);
      return {
        content: [{ type: "text", text: JSON.stringify(response.Result, null, 2) }],
      };
    } catch (e) {
      return errorResult(e);
    }
  }
);

// --- Tool 7: Reverse Geocode ---

server.registerTool(
  "sthan_reverse_geocode",
  {
    title: "Reverse Geocode Coordinates",
    description:
      "Convert latitude/longitude coordinates to the nearest US street address. Returns the address, the distance in meters from the input point, an accuracy type, and a confidence score. " +
      "Use when you have coordinates and need the closest address. US coverage only. " +
      "To go the other way (address to coordinates) use sthan_geocode. " +
      "Read-only with no side effects. Requires a sthan.io API key in STHAN_API_KEY; each call counts toward your plan's rate limit (a free tier is available). On failure it returns an error message.",
    inputSchema: {
      latitude: z.number().min(-90).max(90).describe("Latitude coordinate"),
      longitude: z.number().min(-180).max(180).describe("Longitude coordinate"),
    },
    annotations: READ_ONLY_HINTS,
  },
  async ({ latitude, longitude }) => {
    try {
      const response = await getClient().reverseGeocode(latitude, longitude);
      return {
        content: [{ type: "text", text: JSON.stringify(response.Result, null, 2) }],
      };
    } catch (e) {
      return errorResult(e);
    }
  }
);

// --- Tool 8: IP Geolocation ---

server.registerTool(
  "sthan_ip_geolocation",
  {
    title: "IP Geolocation",
    description:
      "Look up the approximate geographic location of an IPv4 or IPv6 address and the network behind it. Returns country, region, city, coordinates, postal code, timezone with the current local time, flag, currency and calling code, the network (asn, asName, isp, organization), isMobile/isProxy/isHosting flags, reverseDns and a 0-1 confidence score. precision says whether the answer reaches a city, a region or only a country; confidence is absent when the address is new (ask again in a few seconds) or when sources disagreed; an isHosting or isProxy address does not locate a person. " +
      "Use to estimate where an IP is located, for example for analytics or choosing a default region. " +
      "This locates IP addresses, not postal addresses; to work with a street address use sthan_verify_address, sthan_parse_address, or sthan_geocode. " +
      "Read-only with no side effects. Requires a sthan.io API key in STHAN_API_KEY; each call counts toward your plan's rate limit (a free tier is available). On failure it returns an error message.",
    inputSchema: {
      ip: z
        .string()
        .describe("IPv4 (e.g. '8.8.8.8') or IPv6 (e.g. '2001:4860:4860::8888') address"),
    },
    annotations: READ_ONLY_HINTS,
  },
  async ({ ip }) => {
    try {
      const response = await getClient().ipGeolocation(ip);
      return {
        content: [{ type: "text", text: JSON.stringify(response.Result, null, 2) }],
      };
    } catch (e) {
      return errorResult(e);
    }
  }
);

// --- Error helper ---

function errorResult(e: unknown) {
  if (e instanceof SthanApiError) {
    return {
      content: [
        {
          type: "text" as const,
          text: `Error (${e.statusCode}): ${e.message}`,
        },
      ],
      isError: true,
    };
  }
  const msg = e instanceof Error ? e.message : String(e);
  return {
    content: [{ type: "text" as const, text: `Error: ${msg}` }],
    isError: true,
  };
}

// --- Start server ---

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((e) => {
  console.error("Fatal:", e);
  process.exit(1);
});
