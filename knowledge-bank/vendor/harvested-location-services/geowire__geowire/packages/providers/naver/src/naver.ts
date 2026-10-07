import {
  defineProvider,
  errorFromHttpStatus,
  GeoProviderError,
  type GeoProvider,
  type ProviderContext,
} from "@geowirehq/provider-sdk";
import type { SearchPlacesRequest, GeocodeRequest } from "@geowirehq/schema";
import { NAVER_MANIFEST } from "./manifest.js";
import { parseNaverItems, type NaverItem } from "./parse.js";

const DEFAULT_BASE_URL = "https://openapi.naver.com";
const MAX_DISPLAY = 5; // 지역검색 최대 display

export interface NaverOptions {
  /** Naver 애플리케이션 Client ID. clientSecret과 함께 필요(BYOK) */
  clientId?: string;
  /** Naver 애플리케이션 Client Secret */
  clientSecret?: string;
  /** 베이스 URL 오버라이드(테스트·프록시용) */
  baseUrl?: string;
}

/**
 * Naver 지역검색 공급자 — 한국 장소 키워드 검색/지오코딩 (BYOK).
 * 좌표 바이어스·반경은 지원하지 않으며(전국 키워드), 최대 5건을 반환한다.
 */
export function createNaverProvider(options: NaverOptions = {}): GeoProvider {
  const baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");

  function requireCreds(): { id: string; secret: string } {
    if (!options.clientId || !options.clientSecret) {
      throw new GeoProviderError(
        "MISSING_CREDENTIALS",
        "Naver Client ID/Secret이 설정되지 않았습니다",
        { provider: "naver" },
      );
    }
    return { id: options.clientId, secret: options.clientSecret };
  }

  async function localSearch(query: string, limit: number, ctx: ProviderContext): Promise<NaverItem[]> {
    const { id, secret } = requireCreds();
    const url = new URL(`${baseUrl}/v1/search/local.json`);
    url.searchParams.set("query", query);
    url.searchParams.set("display", String(Math.min(Math.max(limit, 1), MAX_DISPLAY)));
    const res = await ctx.fetch(url.toString(), {
      headers: {
        "X-Naver-Client-Id": id,
        "X-Naver-Client-Secret": secret,
        Accept: "application/json",
      },
    });
    if (!res.ok) throw errorFromHttpStatus(res.status, { provider: "naver" });
    const json = (await res.json()) as { items?: NaverItem[] };
    return json.items ?? [];
  }

  return defineProvider({
    manifest: NAVER_MANIFEST,

    async searchPlaces(req: SearchPlacesRequest, ctx) {
      return parseNaverItems(await localSearch(req.query, req.limit ?? MAX_DISPLAY, ctx));
    },

    async geocode(req: GeocodeRequest, ctx) {
      // 지역검색으로 주소 문자열을 조회 → 좌표+정규화 주소
      return parseNaverItems(await localSearch(req.address, req.limit ?? MAX_DISPLAY, ctx));
    },
  });
}
