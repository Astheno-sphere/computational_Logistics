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
} from "@geowirehq/schema";
import { KAKAO_MANIFEST } from "./manifest.js";
import {
  parseKakaoPlaces,
  parseKakaoAddresses,
  parseKakaoReverse,
  type KakaoPlace,
  type KakaoAddressDoc,
} from "./parse.js";

const DEFAULT_BASE_URL = "https://dapi.kakao.com";
const MAX_RADIUS_M = 20_000; // Kakao Local 최대 반경

export interface KakaoOptions {
  /** Kakao REST API 키. 없으면 모든 호출이 MISSING_CREDENTIALS로 실패(BYOK) */
  apiKey?: string;
  /** 베이스 URL 오버라이드(테스트·프록시용) */
  baseUrl?: string;
}

/**
 * Kakao Local(카카오맵) 공급자 — 한국 장소 검색/지오코딩/리버스 (BYOK).
 * x=경도·y=위도(WGS84). keyword 검색은 near+radius로 지역 제한·거리순 정렬을 지원한다.
 */
export function createKakaoProvider(options: KakaoOptions = {}): GeoProvider {
  const baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");

  function requireKey(): string {
    if (!options.apiKey) {
      throw new GeoProviderError("MISSING_CREDENTIALS", "Kakao REST API 키가 설정되지 않았습니다", {
        provider: "kakao",
      });
    }
    return options.apiKey;
  }

  async function get(
    path: string,
    params: Record<string, string | undefined>,
    ctx: ProviderContext,
  ): Promise<unknown> {
    const apiKey = requireKey();
    const url = new URL(`${baseUrl}${path}`);
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== "") url.searchParams.set(k, v);
    }
    const res = await ctx.fetch(url.toString(), {
      headers: { Authorization: `KakaoAK ${apiKey}`, Accept: "application/json" },
    });
    if (!res.ok) throw errorFromHttpStatus(res.status, { provider: "kakao" });
    return res.json();
  }

  return defineProvider({
    manifest: KAKAO_MANIFEST,

    async searchPlaces(req: SearchPlacesRequest, ctx) {
      const hasNear = req.near != null;
      const json = (await get(
        "/v2/local/search/keyword.json",
        {
          query: req.query,
          x: hasNear ? String(req.near!.longitude) : undefined,
          y: hasNear ? String(req.near!.latitude) : undefined,
          radius:
            hasNear && req.radiusMeters != null
              ? String(Math.min(req.radiusMeters, MAX_RADIUS_M))
              : undefined,
          sort: hasNear ? "distance" : undefined, // near가 있으면 거리순
          size: String(Math.min(req.limit ?? 15, 15)),
        },
        ctx,
      )) as { documents?: KakaoPlace[] };
      return parseKakaoPlaces(json.documents);
    },

    async geocode(req: GeocodeRequest, ctx) {
      const json = (await get(
        "/v2/local/search/address.json",
        { query: req.address, size: String(Math.min(req.limit ?? 10, 30)) },
        ctx,
      )) as { documents?: KakaoAddressDoc[] };
      return parseKakaoAddresses(json.documents);
    },

    async reverseGeocode(req: ReverseGeocodeRequest, ctx) {
      const json = (await get(
        "/v2/local/geo/coord2address.json",
        { x: String(req.location.longitude), y: String(req.location.latitude) },
        ctx,
      )) as { documents?: KakaoAddressDoc[] };
      return parseKakaoReverse(json.documents, req.location);
    },
  });
}
