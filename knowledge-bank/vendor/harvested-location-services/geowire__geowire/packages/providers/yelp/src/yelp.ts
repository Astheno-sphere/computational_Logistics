import {
  defineProvider,
  errorFromHttpStatus,
  GeoProviderError,
  type GeoProvider,
  type ProviderContext,
} from "@geowirehq/provider-sdk";
import type { SearchPlacesRequest, GetPlaceRequest } from "@geowirehq/schema";
import { YELP_MANIFEST } from "./manifest.js";
import {
  parseYelpBusiness,
  parseYelpBusinesses,
  type YelpBusiness,
  type YelpReview,
} from "./parse.js";

const DEFAULT_BASE_URL = "https://api.yelp.com/v3";
const MAX_RADIUS_M = 40_000;

export interface YelpOptions {
  /** Yelp Fusion API 키(Bearer). 없으면 MISSING_CREDENTIALS (BYOK) */
  apiKey?: string;
  baseUrl?: string;
}

/**
 * Yelp Fusion 공급자 — 미국·서구권 비즈니스 검색 + 상세(평점·리뷰·가격).
 * search는 좌표(near)가 필요하다(Yelp는 위치 없는 글로벌 키워드 검색 불가).
 * getPlace는 상세 + 리뷰 발췌(최대 3건, Yelp=리뷰 역할)를 함께 가져온다.
 */
export function createYelpProvider(options: YelpOptions = {}): GeoProvider {
  const baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");

  function headers(): Record<string, string> {
    if (!options.apiKey) {
      throw new GeoProviderError("MISSING_CREDENTIALS", "Yelp API 키가 설정되지 않았습니다", {
        provider: "yelp",
      });
    }
    return { Authorization: `Bearer ${options.apiKey}`, Accept: "application/json" };
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
    if (!res.ok) throw errorFromHttpStatus(res.status, { provider: "yelp" });
    return res.json();
  }

  return defineProvider({
    manifest: YELP_MANIFEST,

    async searchPlaces(req: SearchPlacesRequest, ctx) {
      // Yelp search는 위치가 필수 — near가 없으면 폴백을 위해 빈 결과.
      if (!req.near) return [];
      const json = (await get(
        "/businesses/search",
        {
          term: req.query,
          latitude: String(req.near.latitude),
          longitude: String(req.near.longitude),
          radius:
            req.radiusMeters != null
              ? String(Math.min(Math.round(req.radiusMeters), MAX_RADIUS_M))
              : undefined,
          limit: String(Math.min(req.limit ?? 20, 50)),
          locale: req.options?.language ? req.options.language.replace("-", "_") : undefined,
        },
        ctx,
      )) as { businesses?: YelpBusiness[] };
      return parseYelpBusinesses(json.businesses);
    },

    async getPlace(req: GetPlaceRequest, ctx) {
      const detail = (await get(`/businesses/${encodeURIComponent(req.id)}`, {}, ctx)) as YelpBusiness;
      // 리뷰 발췌(최대 3건)를 best-effort로 — Yelp=리뷰 역할. 실패해도 상세는 반환.
      let reviews: YelpReview[] | undefined;
      try {
        const r = (await get(`/businesses/${encodeURIComponent(req.id)}/reviews`, { limit: "3" }, ctx)) as {
          reviews?: YelpReview[];
        };
        reviews = r.reviews;
      } catch {
        reviews = undefined;
      }
      return parseYelpBusiness(detail, reviews);
    },
  });
}
