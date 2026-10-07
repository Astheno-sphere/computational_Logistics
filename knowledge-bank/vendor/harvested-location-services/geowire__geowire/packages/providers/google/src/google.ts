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
  GetPlaceRequest,
  RouteRequest,
  DistanceMatrixRequest,
  LatLng,
  ProviderErrorCode,
} from "@geowirehq/schema";
import { GOOGLE_MANIFEST } from "./manifest.js";
import {
  parseGooglePlace,
  parseGooglePlaces,
  parseGeocodeResults,
  type GooglePlace,
  type GeocodeResult,
} from "./parse.js";
import {
  GOOGLE_TRAVEL_MODE,
  parseGoogleRoutes,
  parseGoogleMatrix,
  type GoogleMatrixElement,
} from "./routes-parse.js";

const DEFAULT_PLACES_BASE = "https://places.googleapis.com/v1";
const DEFAULT_GEOCODE_BASE = "https://maps.googleapis.com/maps/api";
const DEFAULT_ROUTES_BASE = "https://routes.googleapis.com";

/** Place 리소스에서 요청할 필드 (FieldMask; Places API New는 필수) */
const PLACE_FIELDS = [
  "id",
  "displayName",
  "formattedAddress",
  "addressComponents",
  "location",
  "types",
  "primaryType",
  "rating",
  "userRatingCount",
  "regularOpeningHours",
  "nationalPhoneNumber",
  "internationalPhoneNumber",
  "websiteUri",
  "priceLevel",
];

/**
 * getPlace(Place Details) 전용 확장 필드. `reviews`는 Text Search에 붙이면
 * Enterprise+Atmosphere SKU라 검색 비용이 급증하므로 상세 조회에만 요청한다
 * (역할 기반 소싱: 리뷰는 Google이 권위 — search로 후보를 좁힌 뒤 상세에서 채운다).
 */
const DETAIL_FIELDS = [...PLACE_FIELDS, "reviews"];

export interface GoogleOptions {
  /** Google Maps Platform API 키. 없으면 모든 호출이 MISSING_CREDENTIALS로 실패한다(BYOK) */
  apiKey?: string;
  /** Places API (New) 베이스 URL 오버라이드(테스트·프록시용) */
  placesBaseUrl?: string;
  /** Geocoding API 베이스 URL 오버라이드 */
  geocodeBaseUrl?: string;
  /** Routes API 베이스 URL 오버라이드 */
  routesBaseUrl?: string;
  /** 기본 응답 언어(BCP 47). 요청 options.language가 우선 */
  language?: string;
}

/** Geocoding API의 status 필드를 정규화 에러 코드로 매핑 */
function geocodeStatusCode(status: string | undefined): ProviderErrorCode | null {
  switch (status) {
    case "OK":
    case "ZERO_RESULTS":
      return null;
    case "REQUEST_DENIED":
      return "AUTH_FAILED";
    case "OVER_QUERY_LIMIT":
      return "RATE_LIMITED";
    case "INVALID_REQUEST":
      return "INVALID_REQUEST";
    default:
      return "PROVIDER_UNAVAILABLE";
  }
}

/**
 * Google Maps Platform 공급자를 만든다 — **BYOK(Bring Your Own Key)**.
 * 키가 없으면 각 호출이 즉시 `MISSING_CREDENTIALS`를 던져 core가 registry에서
 * skip 처리한다(전체 실패 금지, 설계 §7.1). Places API (New)와 Geocoding API를 함께 쓴다.
 */
export function createGoogleProvider(options: GoogleOptions = {}): GeoProvider {
  const placesBase = (options.placesBaseUrl ?? DEFAULT_PLACES_BASE).replace(/\/+$/, "");
  const geocodeBase = (options.geocodeBaseUrl ?? DEFAULT_GEOCODE_BASE).replace(/\/+$/, "");
  const routesBase = (options.routesBaseUrl ?? DEFAULT_ROUTES_BASE).replace(/\/+$/, "");

  function requireKey(): string {
    if (!options.apiKey) {
      throw new GeoProviderError("MISSING_CREDENTIALS", "Google API 키가 설정되지 않았습니다", {
        provider: "google",
      });
    }
    return options.apiKey;
  }

  /** Places API (New) 호출 (X-Goog-Api-Key + FieldMask 헤더) */
  async function placesFetch(
    path: string,
    init: RequestInit & { fieldMask: string },
    ctx: ProviderContext,
  ): Promise<unknown> {
    const apiKey = requireKey();
    const { fieldMask, ...rest } = init;
    const res = await ctx.fetch(`${placesBase}${path}`, {
      ...rest,
      headers: {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": apiKey,
        "X-Goog-FieldMask": fieldMask,
        ...rest.headers,
      },
    });
    if (!res.ok) throw errorFromHttpStatus(res.status, { provider: "google" });
    return res.json();
  }

  /** Routes API 호출 (POST + X-Goog-Api-Key + X-Goog-FieldMask). 응답 JSON 반환 */
  async function routesFetch(
    path: string,
    body: unknown,
    fieldMask: string,
    ctx: ProviderContext,
  ): Promise<unknown> {
    const apiKey = requireKey();
    const res = await ctx.fetch(`${routesBase}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": apiKey,
        "X-Goog-FieldMask": fieldMask,
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw errorFromHttpStatus(res.status, { provider: "google" });
    return res.json();
  }

  /** Geocoding API 호출 (key 쿼리 파라미터 + status 필드 검사) */
  async function geocodeFetch(
    params: Record<string, string | undefined>,
    ctx: ProviderContext,
  ): Promise<{ results?: GeocodeResult[]; status?: string }> {
    const apiKey = requireKey();
    const url = new URL(`${geocodeBase}/geocode/json`);
    url.searchParams.set("key", apiKey);
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== "") url.searchParams.set(k, v);
    }
    const res = await ctx.fetch(url.toString(), { headers: { Accept: "application/json" } });
    if (!res.ok) throw errorFromHttpStatus(res.status, { provider: "google" });
    const json = (await res.json()) as { results?: GeocodeResult[]; status?: string };
    const code = geocodeStatusCode(json.status);
    if (code) {
      throw new GeoProviderError(code, `Geocoding API status: ${json.status}`, {
        provider: "google",
      });
    }
    return json;
  }

  return defineProvider({
    manifest: GOOGLE_MANIFEST,

    async searchPlaces(req: SearchPlacesRequest, ctx) {
      const body: Record<string, unknown> = {
        textQuery: req.query,
        maxResultCount: req.limit ?? 10,
      };
      const language = req.options?.language ?? options.language;
      if (language) body.languageCode = language;
      if (req.near) {
        body.locationBias = {
          circle: {
            center: { latitude: req.near.latitude, longitude: req.near.longitude },
            radius: req.radiusMeters ?? 5000,
          },
        };
      }
      const json = (await placesFetch(
        "/places:searchText",
        {
          method: "POST",
          body: JSON.stringify(body),
          fieldMask: PLACE_FIELDS.map((f) => `places.${f}`).join(","),
        },
        ctx,
      )) as { places?: GooglePlace[] };
      return parseGooglePlaces(json.places);
    },

    async geocode(req: GeocodeRequest, ctx) {
      const json = await geocodeFetch(
        { address: req.address, region: req.country?.toLowerCase() },
        ctx,
      );
      return parseGeocodeResults(json.results).slice(0, req.limit ?? 5);
    },

    async reverseGeocode(req: ReverseGeocodeRequest, ctx) {
      const json = await geocodeFetch(
        { latlng: `${req.location.latitude},${req.location.longitude}` },
        ctx,
      );
      return parseGeocodeResults(json.results);
    },

    async getPlace(req: GetPlaceRequest, ctx) {
      const json = (await placesFetch(
        `/places/${encodeURIComponent(req.id)}`,
        { method: "GET", fieldMask: DETAIL_FIELDS.join(",") },
        ctx,
      )) as GooglePlace;
      return parseGooglePlace(json);
    },

    async route(req: RouteRequest, ctx) {
      const [origin, ...rest] = req.waypoints;
      const destination = rest.pop()!;
      const intermediates = rest;
      const body: Record<string, unknown> = {
        origin: waypointLatLng(origin!),
        destination: waypointLatLng(destination),
        travelMode: GOOGLE_TRAVEL_MODE[req.mode],
        computeAlternativeRoutes: req.alternatives,
      };
      if (intermediates.length > 0) body.intermediates = intermediates.map(waypointLatLng);
      const fields = ["routes.distanceMeters", "routes.duration", "routes.legs.distanceMeters", "routes.legs.duration"];
      if (req.geometry) {
        body.polylineEncoding = "GEO_JSON_LINESTRING";
        fields.push("routes.polyline.geoJsonLinestring");
      }
      const json = (await routesFetch(
        "/directions/v2:computeRoutes",
        body,
        fields.join(","),
        ctx,
      )) as { routes?: Parameters<typeof parseGoogleRoutes>[0] };
      return parseGoogleRoutes(json.routes);
    },

    async distanceMatrix(req: DistanceMatrixRequest, ctx) {
      const body = {
        origins: req.origins.map(matrixWaypoint),
        destinations: req.destinations.map(matrixWaypoint),
        travelMode: GOOGLE_TRAVEL_MODE[req.mode],
      };
      const json = (await routesFetch(
        "/distanceMatrix/v2:computeRouteMatrix",
        body,
        "originIndex,destinationIndex,distanceMeters,duration,condition",
        ctx,
      )) as GoogleMatrixElement[];
      return parseGoogleMatrix(json, req.origins.length, req.destinations.length);
    },
  });
}

/** LatLng → Routes API waypoint(location.latLng) */
function waypointLatLng(p: LatLng): { location: { latLng: { latitude: number; longitude: number } } } {
  return { location: { latLng: { latitude: p.latitude, longitude: p.longitude } } };
}

/** LatLng → Route Matrix waypoint(waypoint.location.latLng) */
function matrixWaypoint(p: LatLng): { waypoint: ReturnType<typeof waypointLatLng> } {
  return { waypoint: waypointLatLng(p) };
}
