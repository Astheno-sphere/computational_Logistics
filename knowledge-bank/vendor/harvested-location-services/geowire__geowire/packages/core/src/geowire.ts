import type { GeoProvider, Logger, Clock, FetchFn } from "@geowirehq/provider-sdk";
import { noopLogger } from "@geowirehq/provider-sdk";
import type { Capability } from "@geowirehq/schema";
import {
  SearchPlacesRequest,
  GeocodeRequest,
  ReverseGeocodeRequest,
  GetPlaceRequest,
  SearchPlacesResponse,
  RouteRequest,
  RouteResponse,
  DistanceMatrixRequest,
  DistanceMatrixResponse,
  AreaInsightsRequest,
  AreaInsightsResponse,
  DemographicsRequest,
  DemographicsResponse,
  IsochroneRequest,
  IsochroneResponse,
  Place,
} from "@geowirehq/schema";
import { GeoWireConfig, defaultConfig } from "./config/schema.js";
import { normalizeConfig } from "./config/load.js";
import { collectConfigWarnings } from "./config/warnings.js";
import { ProviderRegistry } from "./registry.js";
import { runOperation } from "./pipeline/pipeline.js";
import { runGetPlace } from "./pipeline/get-place.js";
import { runRoute, runDistanceMatrix, runDemographics } from "./pipeline/routing.js";
import { runAreaInsights } from "./analysis/area.js";
import { runIsochrone } from "./analysis/isochrone.js";
import { resolveCountry } from "./pipeline/normalize-request.js";
import type { OperationSpec } from "./pipeline/types.js";
import { MemoryCache } from "./cache/memory.js";
import type { CacheAdapter } from "./cache/adapter.js";
import { CostTracker } from "./cost.js";
import { CircuitBreaker } from "./circuit-breaker.js";

/** `createGeoWire()` 옵션 */
export interface CreateGeoWireOptions {
  /**
   * 등록할 provider 인스턴스들. core는 provider 패키지에 의존하지 않으므로
   * 호출자(CLI/server/테스트)가 생성해 주입한다(예: `createNominatimProvider()`).
   */
  providers?: readonly GeoProvider[];
  /** 인라인 config 객체. 파일 로딩은 loadConfig()로 미리 수행해 넘긴다 */
  config?: GeoWireConfig | Record<string, unknown>;
  /** 구조적 로거. 기본 noop */
  logger?: Logger;
  /** 시계 주입(테스트용). 기본 Date.now */
  now?: Clock;
  /** 하위 fetch 주입(테스트용). 기본 전역 fetch */
  baseFetch?: FetchFn;
  /** 캐시 어댑터 주입. 기본 config.cache 기반 MemoryCache */
  cache?: CacheAdapter;
}

/** provider 상태 노출용 요약 (list_geo_providers / GET /v1/providers) */
export interface ProviderInfo {
  id: string;
  name: string;
  enabled: boolean;
  priority: number;
  capabilities: Capability[];
  authType: "apiKey" | "oauth" | "none";
  attributionRequired?: string;
}

/**
 * GeoWire 퍼사드 — SDK embedded 모드의 진입점(설계 §9.3).
 * config·registry·공통 실행 의존성을 보관하고, 파이프라인을 구동한다.
 *
 * 검색/지오코딩 메서드는 M2(pipeline)에서 이 클래스에 추가된다.
 */
export class GeoWire {
  readonly config: GeoWireConfig;
  readonly registry: ProviderRegistry;
  readonly logger: Logger;
  readonly now: Clock;
  readonly baseFetch: FetchFn;
  readonly cache: CacheAdapter;
  readonly costTracker: CostTracker;
  readonly circuitBreaker: CircuitBreaker;

  constructor(options: CreateGeoWireOptions = {}) {
    this.config = options.config ? normalizeConfig(options.config) : defaultConfig();
    this.logger = options.logger ?? noopLogger;
    this.now = options.now ?? Date.now;
    this.baseFetch = options.baseFetch ?? ((url, init) => fetch(url, init));
    this.registry = new ProviderRegistry(options.providers ?? [], this.config);
    this.cache =
      options.cache ??
      new MemoryCache({ maxEntries: this.config.cache.maxEntries, now: this.now });
    this.costTracker = new CostTracker();
    this.circuitBreaker = new CircuitBreaker({ now: this.now });

    for (const warning of collectConfigWarnings(this.config, this.registry.ids())) {
      this.logger.warn(`[config:${warning.code}] ${warning.message}`);
    }
  }

  /**
   * 자연어 + 좌표/지역 기반 장소 검색 (설계 §7 파이프라인).
   * 입력을 Zod로 검증하고, 응답도 `SearchPlacesResponse`로 자기 검증한다(런타임 계약 보증).
   */
  async searchPlaces(input: unknown): Promise<SearchPlacesResponse> {
    const req = SearchPlacesRequest.parse(input);
    const spec: OperationSpec = {
      capability: "search",
      method: "searchPlaces",
      request: req,
      country: resolveCountry(req.country, req.near),
      near: req.near,
      radiusMeters: req.radiusMeters,
      limit: req.limit,
      options: req.options,
    };
    const { results, meta } = await runOperation(this, spec);
    return SearchPlacesResponse.parse({ results, meta });
  }

  /** 주소 → 좌표 (+정규화 주소). search와 동일 파이프라인, geocode capability */
  async geocode(input: unknown): Promise<SearchPlacesResponse> {
    const req = GeocodeRequest.parse(input);
    const spec: OperationSpec = {
      capability: "geocode",
      method: "geocode",
      request: req,
      country: req.country,
      limit: req.limit,
      options: req.options,
    };
    const { results, meta } = await runOperation(this, spec);
    return SearchPlacesResponse.parse({ results, meta });
  }

  /** 좌표 → 주소 */
  async reverseGeocode(input: unknown): Promise<SearchPlacesResponse> {
    const req = ReverseGeocodeRequest.parse(input);
    const spec: OperationSpec = {
      capability: "reverseGeocode",
      method: "reverseGeocode",
      request: req,
      options: req.options,
    };
    const { results, meta } = await runOperation(this, spec);
    return SearchPlacesResponse.parse({ results, meta });
  }

  /**
   * 단일 장소 상세 조회 (설계 §9.1). `provider:providerPlaceId` 참조를 받는다.
   * 내부 `gwp_` ID는 역추적 불가라 `null`을 돌려준다(v0.1). 없으면 `null`.
   */
  async getPlace(input: unknown): Promise<Place | null> {
    const req = GetPlaceRequest.parse(input);
    const place = await runGetPlace(this, req);
    return place ? Place.parse(place) : null;
  }

  /**
   * 길찾기 (설계: routing/v1). 경유지 간 경로를 route capable 공급자에서 first-success로 얻는다.
   * 무키 OSRM이 기본. 응답도 `RouteResponse`로 자기 검증한다.
   */
  async getRoute(input: unknown): Promise<RouteResponse> {
    const req = RouteRequest.parse(input);
    const { routes, meta } = await runRoute(this, req);
    return RouteResponse.parse({ routes, meta });
  }

  /** 거리/시간 행렬. origins×destinations를 distanceMatrix capable 공급자에서 계산한다. */
  async getDistanceMatrix(input: unknown): Promise<DistanceMatrixResponse> {
    const req = DistanceMatrixRequest.parse(input);
    const { matrix, meta } = await runDistanceMatrix(this, req);
    if (!matrix) {
      throw new Error("사용 가능한 distanceMatrix 공급자가 없습니다 (OSRM 등록 필요)");
    }
    return DistanceMatrixResponse.parse({ matrix, meta });
  }

  /**
   * 지점이 속한 지역의 인구통계 (설계: demographics/v1). demographics capable 공급자에서
   * first-success로 얻는다(예: US Census). 커버 못 하면 profile은 null.
   */
  async getDemographics(input: unknown): Promise<DemographicsResponse> {
    const req = DemographicsRequest.parse(input);
    const { profile, meta } = await runDemographics(this, req);
    return DemographicsResponse.parse({ profile, meta });
  }

  /**
   * 지역/상권 분석 (설계: analysis/v1). 중심점 반경 내 업종별 밀도·경쟁·평점 지형을 집계한다.
   * 검색 파이프라인 위에 쌓는 상위 레이어. 응답도 `AreaInsightsResponse`로 자기 검증한다.
   */
  async analyzeArea(input: unknown): Promise<AreaInsightsResponse> {
    const req = AreaInsightsRequest.parse(input);
    const { insights, meta } = await runAreaInsights(this, req);
    return AreaInsightsResponse.parse({ insights, meta });
  }

  /**
   * 도달권(isochrone) 근사 (설계: isochrone/v1). 출발점에서 N분 내 도달 가능 영역을
   * 거리행렬(무키 OSRM 등) 위에서 근사한다. 계산할 공급자가 없으면 isochrone은 null.
   */
  async getIsochrone(input: unknown): Promise<IsochroneResponse> {
    const req = IsochroneRequest.parse(input);
    const { isochrone, meta } = await runIsochrone(this, req);
    return IsochroneResponse.parse({ isochrone, meta });
  }

  /** 활성/비활성 공급자 요약. list_geo_providers·/v1/providers의 데이터원 */
  listProviders(): ProviderInfo[] {
    return this.registry.all().map((r) => ({
      id: r.id,
      name: r.provider.manifest.name,
      enabled: r.enabled,
      priority: r.priority,
      capabilities: [...r.provider.manifest.capabilities],
      authType: r.provider.manifest.authType,
      attributionRequired: r.provider.manifest.policy.attributionRequired,
    }));
  }
}

/**
 * GeoWire 인스턴스를 만든다 — 임베디드 SDK의 진입점.
 * ```ts
 * const geo = createGeoWire({ providers: [createNominatimProvider()] });
 * ```
 */
export function createGeoWire(options: CreateGeoWireOptions = {}): GeoWire {
  return new GeoWire(options);
}
