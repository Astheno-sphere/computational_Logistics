import {
  defineProvider,
  errorFromHttpStatus,
  GeoProviderError,
  type GeoProvider,
  type ProviderContext,
} from "@geowirehq/provider-sdk";
import type { SearchPlacesRequest, GetPlaceRequest } from "@geowirehq/schema";
import { FOURSQUARE_MANIFEST } from "./manifest.js";
import { parseFsqPlace, parseFsqPlaces, type FsqPlace } from "./parse.js";

const DEFAULT_BASE_URL = "https://places-api.foursquare.com";
const DEFAULT_API_VERSION = "2025-06-17";
const MAX_RADIUS_M = 100_000;
const FIELDS =
  "fsq_place_id,name,latitude,longitude,location,categories,tel,website,rating,price,photos,popularity";

export interface FoursquareOptions {
  /** Foursquare Service API key (Bearer). 없으면 MISSING_CREDENTIALS (BYOK) */
  apiKey?: string;
  /** X-Places-Api-Version 헤더 (기본 2025-06-17) */
  apiVersion?: string;
  baseUrl?: string;
}

/**
 * Foursquare Places 공급자 — 글로벌 POI 검색 + 상세 (BYOK).
 * 현행 API(places-api.foursquare.com): Bearer 인증 + X-Places-Api-Version 헤더, 좌표는 WGS84.
 */
export function createFoursquareProvider(options: FoursquareOptions = {}): GeoProvider {
  const baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
  const apiVersion = options.apiVersion ?? DEFAULT_API_VERSION;

  function headers(): Record<string, string> {
    if (!options.apiKey) {
      throw new GeoProviderError("MISSING_CREDENTIALS", "Foursquare API 키가 설정되지 않았습니다", {
        provider: "foursquare",
      });
    }
    return {
      Authorization: `Bearer ${options.apiKey}`,
      "X-Places-Api-Version": apiVersion,
      Accept: "application/json",
    };
  }

  async function get(
    path: string,
    params: Record<string, string | undefined>,
    ctx: ProviderContext,
  ): Promise<unknown> {
    const h = headers();
    const url = new URL(`${baseUrl}${path}`);
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== "") url.searchParams.set(k, v);
    }
    const res = await ctx.fetch(url.toString(), { headers: h });
    if (!res.ok) throw errorFromHttpStatus(res.status, { provider: "foursquare" });
    return res.json();
  }

  return defineProvider({
    manifest: FOURSQUARE_MANIFEST,

    async searchPlaces(req: SearchPlacesRequest, ctx) {
      const json = (await get(
        "/places/search",
        {
          query: req.query,
          ll: req.near ? `${req.near.latitude},${req.near.longitude}` : undefined,
          radius:
            req.near && req.radiusMeters != null
              ? String(Math.min(req.radiusMeters, MAX_RADIUS_M))
              : undefined,
          limit: String(Math.min(req.limit ?? 10, 50)),
          fields: FIELDS,
        },
        ctx,
      )) as { results?: FsqPlace[] };
      return parseFsqPlaces(json.results);
    },

    async getPlace(req: GetPlaceRequest, ctx) {
      const json = (await get(
        `/places/${encodeURIComponent(req.id)}`,
        { fields: FIELDS },
        ctx,
      )) as FsqPlace;
      return parseFsqPlace(json);
    },
  });
}
