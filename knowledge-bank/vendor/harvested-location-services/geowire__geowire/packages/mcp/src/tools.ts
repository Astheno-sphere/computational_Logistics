import { z } from "zod";
import {
  SearchPlacesRequest,
  GeocodeRequest,
  ReverseGeocodeRequest,
  GetPlaceRequest,
  RouteRequest,
  DistanceMatrixRequest,
  AreaInsightsRequest,
  DemographicsRequest,
  IsochroneRequest,
} from "@geowirehq/schema";
import type { GeoWire } from "@geowirehq/core";
import { GeoProviderError } from "@geowirehq/provider-sdk";
import type { CallToolResult, Tool } from "@modelcontextprotocol/sdk/types.js";
import {
  formatResults,
  formatSinglePlace,
  formatProviders,
  formatRoutes,
  formatMatrix,
  formatAreaInsights,
  formatDemographics,
  formatIsochrone,
} from "./format.js";

/**
 * Zod 스키마를 MCP inputSchema(JSON Schema)로 변환한다 (설계 §9.1 "수기 금지, 자동 생성").
 * - `$schema` 메타 키 제거(MCP inputSchema에 불필요)
 * - default가 있는 필드는 required에서 제외(클라이언트가 생략 가능함을 정확히 광고)
 */
function toInputSchema(schema: z.ZodType): Tool["inputSchema"] {
  const json = z.toJSONSchema(schema) as Record<string, unknown> & {
    properties?: Record<string, { default?: unknown }>;
    required?: string[];
  };
  delete json.$schema;
  if (json.required && json.properties) {
    json.required = json.required.filter((key) => json.properties![key]?.default === undefined);
    if (json.required.length === 0) delete json.required;
  }
  return json as Tool["inputSchema"];
}

const EMPTY_INPUT: Tool["inputSchema"] = {
  type: "object",
  properties: {},
  additionalProperties: false,
};

/**
 * 도구 설명문 = 제품 (설계 §9.1).
 * LLM이 올바른 도구를 고르고 인자를 채우도록 목적·구분·예시를 명시한다.
 */
export const TOOL_DEFS: Tool[] = [
  {
    name: "search_places",
    description:
      "Search for places (businesses, points of interest, landmarks) by a natural-language query, " +
      "optionally biased to a coordinate (`near`) and/or restricted to a country. Returns places ranked " +
      "by relevance/distance, each with location, address, contact, opening hours, and its data source(s). " +
      "Use this for 'find X near Y' requests. " +
      'Example: {"query": "24-hour pharmacy", "near": {"latitude": 10.7769, "longitude": 106.7009}, "radiusMeters": 2000}. ' +
      "To turn an address into coordinates use geocode_address instead; to look up one known place use get_place.",
    inputSchema: toInputSchema(SearchPlacesRequest),
  },
  {
    name: "get_place",
    description:
      "Fetch full details for a single place by its provider reference id, in the form " +
      "'provider:providerPlaceId' (e.g. 'google:ChIJN1t_tDeuEmsRUsoyG83frY4'), as found in a place's `sources`. " +
      "Only providers that support getPlace can resolve a reference — currently Google (needs an API key). " +
      "OpenStreetMap/Nominatim does not, so a 'nominatim:...' reference returns nothing; use search_places or " +
      "geocode_address for OSM instead. Internal 'gwp_' ids cannot be resolved directly. " +
      'Example: {"id": "google:ChIJN1t_tDeuEmsRUsoyG83frY4"}.',
    inputSchema: toInputSchema(GetPlaceRequest),
  },
  {
    name: "geocode_address",
    description:
      "Convert a street address or place name into geographic coordinates and a normalized address. " +
      "Use this when you have an address string and need latitude/longitude. " +
      'Example: {"address": "1600 Amphitheatre Parkway, Mountain View, CA"}. ' +
      "To search for businesses by name/category, use search_places.",
    inputSchema: toInputSchema(GeocodeRequest),
  },
  {
    name: "reverse_geocode",
    description:
      "Convert geographic coordinates into the nearest address / place. " +
      'Example: {"location": {"latitude": 37.5665, "longitude": 126.9780}}.',
    inputSchema: toInputSchema(ReverseGeocodeRequest),
  },
  {
    name: "get_directions",
    description:
      "Get a route (driving directions) between two or more waypoints, with total distance, travel time, " +
      "and per-leg breakdown. Works with no API key (OpenStreetMap routing via OSRM). Use this for " +
      "'how do I get from A to B', 'how far by car', or 'how long to drive' questions. Waypoints are " +
      "{latitude, longitude} in order (start, [via...], end). " +
      'Example: {"waypoints": [{"latitude": 37.5665, "longitude": 126.9780}, {"latitude": 37.4979, "longitude": 127.0276}]}. ' +
      "Set geometry:true to also get the route polyline. Note: the public OSRM server supports driving only.",
    inputSchema: toInputSchema(RouteRequest),
  },
  {
    name: "distance_matrix",
    description:
      "Compute a matrix of travel distances and times from each origin to each destination (N origins × M " +
      "destinations) in one call. No API key needed. Use this to rank/compare many candidates by drive time — " +
      "e.g. 'which of these 5 stores is closest to the customer' or delivery/logistics assignment. " +
      'Example: {"origins": [{"latitude": 37.57, "longitude": 126.98}], "destinations": [{"latitude": 37.49, "longitude": 127.02}, {"latitude": 37.51, "longitude": 127.05}]}. ' +
      "rows[i][j] is origins[i] → destinations[j]. Public OSRM supports driving only.",
    inputSchema: toInputSchema(DistanceMatrixRequest),
  },
  {
    name: "analyze_area",
    description:
      "Analyze a commercial area / neighborhood: given a center point, radius, and business types, " +
      "return how many of each exist nearby, their density (per km²), rating landscape, and top places. " +
      "Use this for market/competition questions — 'how saturated is coffee here', 'is this a good spot " +
      "for a bakery', 'what's the dining scene within 1km'. " +
      'Example: {"center": {"latitude": 37.4979, "longitude": 127.0276}, "radiusMeters": 1000, "categories": ["cafe", "restaurant", "convenience store"]}. ' +
      "Works with any configured providers; richer with Google/Foursquare (ratings). Not demographic data — " +
      "it's a place-density/competition view built from live search.",
    inputSchema: toInputSchema(AreaInsightsRequest),
  },
  {
    name: "get_demographics",
    description:
      "Get demographics (population, median age, median household income, households) for the area " +
      "containing a coordinate. Use this for market context — 'who lives around here', income/age of an " +
      "area. Requires a demographics provider: US Census (free key, US only). Returns null outside coverage. " +
      'Example: {"location": {"latitude": 37.7749, "longitude": -122.4194}}. ' +
      "For a full commercial picture combine with analyze_area, which folds this in automatically.",
    inputSchema: toInputSchema(DemographicsRequest),
  },
  {
    name: "get_isochrone",
    description:
      "Compute a travel-time reachability area (isochrone): from an origin, the region reachable within N " +
      "minutes of driving/walking/cycling, as a GeoJSON polygon + area in km². No API key (OpenStreetMap " +
      "routing). Use for site selection / catchment questions — 'what's within a 15-minute drive', 'how big " +
      "is this store's 10-min catchment'. " +
      'Example: {"origin": {"latitude": 37.7749, "longitude": -122.4194}, "minutes": 15, "mode": "driving"}. ' +
      "It's an approximation (sampled bearings scored by a distance matrix), not a routing-engine isochrone.",
    inputSchema: toInputSchema(IsochroneRequest),
  },
  {
    name: "list_geo_providers",
    description:
      "List the geo data providers currently configured, with their capabilities, enabled state, priority, " +
      "and required attribution. Use this to understand which data sources are available (e.g. whether Google " +
      "is configured) before choosing a strategy or explaining coverage. Takes no arguments.",
    inputSchema: EMPTY_INPUT,
  },
];

function textResult(text: string, structuredContent?: Record<string, unknown>): CallToolResult {
  const result: CallToolResult = { content: [{ type: "text", text }] };
  if (structuredContent) result.structuredContent = structuredContent;
  return result;
}

function errorResult(text: string): CallToolResult {
  return { content: [{ type: "text", text }], isError: true };
}

/** Zod 검증 실패를 LLM이 자가 수정 가능한 메시지로 (설계 §9.1) */
function formatZodError(toolName: string, err: z.ZodError): string {
  const issues = err.issues
    .map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`)
    .join("; ");
  return `Invalid arguments for ${toolName}: ${issues}.`;
}

/**
 * 도구 호출을 GeoWire 퍼사드로 위임한다.
 * 응답은 사람이 읽는 요약 텍스트 + `structuredContent`(스키마 준수 JSON)를 함께 담는다.
 */
export async function dispatchTool(
  geo: GeoWire,
  name: string,
  args: Record<string, unknown>,
): Promise<CallToolResult> {
  try {
    switch (name) {
      case "search_places": {
        const res = await geo.searchPlaces(args);
        return textResult(formatResults(res.results, res.meta), res);
      }
      case "geocode_address": {
        const res = await geo.geocode(args);
        return textResult(formatResults(res.results, res.meta), res);
      }
      case "reverse_geocode": {
        const res = await geo.reverseGeocode(args);
        return textResult(formatResults(res.results, res.meta), res);
      }
      case "get_place": {
        const parsed = GetPlaceRequest.parse(args);
        const place = await geo.getPlace(parsed);
        return textResult(formatSinglePlace(place, parsed.id), { place });
      }
      case "get_directions": {
        const res = await geo.getRoute(args);
        return textResult(formatRoutes(res.routes, res.meta), res);
      }
      case "distance_matrix": {
        const res = await geo.getDistanceMatrix(args);
        return textResult(formatMatrix(res.matrix, res.meta), res);
      }
      case "analyze_area": {
        const res = await geo.analyzeArea(args);
        return textResult(formatAreaInsights(res.insights, res.meta), res);
      }
      case "get_demographics": {
        const res = await geo.getDemographics(args);
        return textResult(formatDemographics(res.profile, res.meta), res);
      }
      case "get_isochrone": {
        const res = await geo.getIsochrone(args);
        return textResult(formatIsochrone(res.isochrone, res.meta), res);
      }
      case "list_geo_providers": {
        const providers = geo.listProviders();
        return textResult(formatProviders(providers), { providers });
      }
      default:
        return errorResult(`Unknown tool: ${name}`);
    }
  } catch (err) {
    if (err instanceof z.ZodError) return errorResult(formatZodError(name, err));
    if (err instanceof GeoProviderError) {
      return errorResult(`Provider error (${err.code}) from ${err.provider ?? "provider"}: ${err.message}`);
    }
    return errorResult(`Tool ${name} failed: ${err instanceof Error ? err.message : String(err)}`);
  }
}
