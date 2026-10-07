import {
  defineProvider,
  errorFromHttpStatus,
  type GeoProvider,
  type ProviderContext,
} from "@geowirehq/provider-sdk";
import type {
  SearchPlacesRequest,
  GeocodeRequest,
  ReverseGeocodeRequest,
} from "@geowirehq/schema";
import { NOMINATIM_MANIFEST } from "./manifest.js";
import { RateLimiter } from "./rate-limit.js";
import { parseResults } from "./parse.js";

const VERSION = "0.1.0";
const DEFAULT_BASE_URL = "https://nominatim.openstreetmap.org";
const METERS_PER_DEG_LAT = 111_320;
/** near만 주어지고 radiusMeters가 없을 때 검색을 편향(bias)시킬 기본 반경 */
const DEFAULT_BIAS_RADIUS_M = 25_000;

/**
 * near(+반경)를 Nominatim `viewbox`(경도/위도 경계상자)로 변환한다.
 * radiusMeters가 명시되면 `bounded=1`로 해당 상자에 **하드 제한**하고,
 * near만 있으면 viewbox는 우선순위 편향(bias)으로만 작동한다(밖 결과도 허용).
 */
function viewboxParams(
  near: { latitude: number; longitude: number },
  radiusMeters?: number,
): { viewbox: string; bounded?: string } {
  const radius = radiusMeters ?? DEFAULT_BIAS_RADIUS_M;
  const latDelta = radius / METERS_PER_DEG_LAT;
  const cosLat = Math.max(Math.cos((near.latitude * Math.PI) / 180), 0.01);
  const lonDelta = radius / (METERS_PER_DEG_LAT * cosLat);
  // 좌표를 유효 범위로 clamp — 날짜변경선(경도 ±180)·극지방(위도 ±90) 근처에서
  // Nominatim이 거부/오동작하는 out-of-range viewbox를 방출하지 않도록.
  const clampLat = (v: number): number => Math.min(90, Math.max(-90, v));
  const clampLon = (v: number): number => Math.min(180, Math.max(-180, v));
  const left = clampLon(near.longitude - lonDelta);
  const right = clampLon(near.longitude + lonDelta);
  const top = clampLat(near.latitude + latDelta);
  const bottom = clampLat(near.latitude - latDelta);
  const viewbox = `${left},${top},${right},${bottom}`;
  return radiusMeters != null ? { viewbox, bounded: "1" } : { viewbox };
}

export interface NominatimOptions {
  /** 자체 호스팅 Nominatim으로 전환 (공용 서버 부하 회피) */
  baseUrl?: string;
  /** 필수 User-Agent. 기본값은 프로젝트 식별 UA */
  userAgent?: string;
  /** OSM 정책 권장 연락 이메일 (쿼리에 첨부) */
  email?: string;
  /** 초당 요청 상한. 기본 1 (공용 서버 예절) */
  requestsPerSecond?: number;
  /** 대기 구현 주입 (테스트용). 기본 setTimeout */
  sleep?: (ms: number) => Promise<void>;
}

/**
 * Nominatim(OpenStreetMap) 공급자를 만든다 — **키 불필요, Zero-config의 근간(P1)**.
 * 1 req/s rate limit과 식별 User-Agent를 내부에서 강제한다(호출자가 끌 수 없음).
 */
export function createNominatimProvider(options: NominatimOptions = {}): GeoProvider {
  const baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
  const userAgent = options.userAgent ?? `geowire/${VERSION} (+https://geowire.dev)`;
  const intervalMs = 1000 / (options.requestsPerSecond ?? 1);
  const sleep = options.sleep ?? ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
  const limiter = new RateLimiter(intervalMs, sleep);

  async function request(
    path: string,
    params: Record<string, string | undefined>,
    ctx: ProviderContext,
  ): Promise<unknown> {
    await limiter.acquire(ctx.now());
    const url = new URL(`${baseUrl}${path}`);
    url.searchParams.set("format", "jsonv2");
    url.searchParams.set("addressdetails", "1");
    for (const [key, value] of Object.entries(params)) {
      if (value != null && value !== "") url.searchParams.set(key, value);
    }
    if (options.email) url.searchParams.set("email", options.email);

    const res = await ctx.fetch(url.toString(), {
      headers: { "User-Agent": userAgent, Accept: "application/json" },
    });
    if (!res.ok) throw errorFromHttpStatus(res.status, { provider: "nominatim" });
    return res.json();
  }

  return defineProvider({
    manifest: NOMINATIM_MANIFEST,

    async searchPlaces(req: SearchPlacesRequest, ctx) {
      // near가 있으면 viewbox로 지역 제한/편향 — 없으면 전역 이름 검색이 되어
      // "강남 근처 X"가 다른 대륙 결과를 반환하는 문제가 생긴다.
      const raw = await request(
        "/search",
        {
          q: req.query,
          limit: String(req.limit ?? 10),
          countrycodes: req.country?.toLowerCase(),
          ...(req.near ? viewboxParams(req.near, req.radiusMeters) : {}),
        },
        ctx,
      );
      return parseResults(raw);
    },

    async geocode(req: GeocodeRequest, ctx) {
      const raw = await request(
        "/search",
        {
          q: req.address,
          limit: String(req.limit ?? 5),
          countrycodes: req.country?.toLowerCase(),
        },
        ctx,
      );
      return parseResults(raw);
    },

    async reverseGeocode(req: ReverseGeocodeRequest, ctx) {
      const raw = await request(
        "/reverse",
        {
          lat: String(req.location.latitude),
          lon: String(req.location.longitude),
        },
        ctx,
      );
      return parseResults(raw);
    },
  });
}
