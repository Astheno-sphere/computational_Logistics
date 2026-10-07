import {
  defineProvider,
  errorFromHttpStatus,
  GeoProviderError,
  type GeoProvider,
  type ProviderContext,
} from "@geowirehq/provider-sdk";
import type {
  SearchPlacesRequest,
  GeocodeRequest,
  ReverseGeocodeRequest,
  ProviderErrorCode,
} from "@geowirehq/schema";
import { BAIDU_MANIFEST } from "./manifest.js";
import {
  parseBaiduPlaces,
  parseBaiduGeocode,
  parseBaiduReverse,
  type BaiduPlace,
  type BaiduGeocode,
  type BaiduReverse,
} from "./parse.js";

const DEFAULT_BASE_URL = "https://api.map.baidu.com";
const MAX_RADIUS_M = 50_000;

export interface BaiduOptions {
  /** Baidu Web 서비스 AK. 없으면 MISSING_CREDENTIALS (BYOK) */
  apiKey?: string;
  baseUrl?: string;
}

/** Baidu status 필드 → 정규화 에러 코드 (0 = 성공) */
function baiduStatusCode(status: number | undefined): ProviderErrorCode | null {
  switch (status) {
    case 0:
      return null;
    case 101:
    case 102:
    case 200:
    case 211:
      return "AUTH_FAILED";
    case 210:
    case 302:
    case 401:
      return "QUOTA_EXCEEDED";
    default:
      return "PROVIDER_UNAVAILABLE";
  }
}

/**
 * Baidu Maps(百度地图) 공급자 — 중국 장소 검색/지오코딩/리버스 (BYOK).
 * 입력 좌표는 `coord_type/coordtype=wgs84`로 보내고, 출력 BD-09 좌표는 WGS84로 변환한다.
 * place 검색은 `near`(중심+반경)가 있어야 동작한다(없으면 빈 결과 → 폴백).
 */
export function createBaiduProvider(options: BaiduOptions = {}): GeoProvider {
  const baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");

  function requireKey(): string {
    if (!options.apiKey) {
      throw new GeoProviderError("MISSING_CREDENTIALS", "Baidu AK가 설정되지 않았습니다", {
        provider: "baidu",
      });
    }
    return options.apiKey;
  }

  async function get<T extends { status?: number }>(
    path: string,
    params: Record<string, string | undefined>,
    ctx: ProviderContext,
  ): Promise<T> {
    const ak = requireKey();
    const url = new URL(`${baseUrl}${path}`);
    url.searchParams.set("output", "json");
    url.searchParams.set("ak", ak);
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== "") url.searchParams.set(k, v);
    }
    const res = await ctx.fetch(url.toString(), { headers: { Accept: "application/json" } });
    if (!res.ok) throw errorFromHttpStatus(res.status, { provider: "baidu" });
    const json = (await res.json()) as T;
    const code = baiduStatusCode(json.status);
    if (code) {
      throw new GeoProviderError(code, `Baidu status: ${json.status}`, { provider: "baidu" });
    }
    return json;
  }

  return defineProvider({
    manifest: BAIDU_MANIFEST,

    async searchPlaces(req: SearchPlacesRequest, ctx) {
      if (!req.near) return []; // Baidu place 검색은 중심 좌표(또는 region)가 필요 → 폴백
      const json = await get<{ status?: number; results?: BaiduPlace[] }>(
        "/place/v2/search",
        {
          query: req.query,
          location: `${req.near.latitude},${req.near.longitude}`,
          coord_type: "1", // 입력 = WGS84
          radius: String(Math.min(req.radiusMeters ?? MAX_RADIUS_M, MAX_RADIUS_M)),
          scope: "2", // 상세(tag·telephone) 포함
          page_size: String(Math.min(req.limit ?? 10, 20)),
        },
        ctx,
      );
      return parseBaiduPlaces(json.results);
    },

    async geocode(req: GeocodeRequest, ctx) {
      const json = await get<{ status?: number; result?: BaiduGeocode }>(
        "/geocoding/v3/",
        { address: req.address },
        ctx,
      );
      return parseBaiduGeocode(json.result, req.address);
    },

    async reverseGeocode(req: ReverseGeocodeRequest, ctx) {
      const json = await get<{ status?: number; result?: BaiduReverse }>(
        "/reverse_geocoding/v3/",
        {
          location: `${req.location.latitude},${req.location.longitude}`,
          coordtype: "wgs84ll", // 입력 = WGS84
        },
        ctx,
      );
      return parseBaiduReverse(json.result, req.location);
    },
  });
}
