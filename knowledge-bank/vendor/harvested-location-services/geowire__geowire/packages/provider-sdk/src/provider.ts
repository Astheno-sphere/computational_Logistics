import type {
  Capability,
  ProviderManifest,
  SearchPlacesRequest,
  GeocodeRequest,
  ReverseGeocodeRequest,
  GetPlaceRequest,
  AutocompleteRequest,
  RouteRequest,
  DistanceMatrixRequest,
  DemographicsRequest,
} from "@geowirehq/schema";
import type { ProviderContext } from "./context.js";
import type {
  ProviderHealth,
  ProviderPlace,
  ProviderRoute,
  ProviderDistanceMatrix,
  ProviderDemographics,
} from "./types.js";

/**
 * 모든 GeoWire 공급자가 구현하는 계약.
 * capability 메서드는 전부 선택적이며, `manifest.capabilities`에 선언한 것과 실제 구현이
 * 일치하는지는 `defineProvider()`가 생성 시점에 검증한다.
 *
 * 각 메서드는 **정규화된 `ProviderPlace` 목록**을 반환한다 — 내부 ID·attribution·병합은
 * core의 몫이다. 실패는 반드시 `GeoProviderError`로 던진다.
 */
export interface GeoProvider {
  /** 기계가 읽는 공급자 선언 (capability·커버리지·비용·정책) */
  readonly manifest: ProviderManifest;

  searchPlaces?(req: SearchPlacesRequest, ctx: ProviderContext): Promise<ProviderPlace[]>;
  geocode?(req: GeocodeRequest, ctx: ProviderContext): Promise<ProviderPlace[]>;
  reverseGeocode?(
    req: ReverseGeocodeRequest,
    ctx: ProviderContext,
  ): Promise<ProviderPlace[]>;
  getPlace?(req: GetPlaceRequest, ctx: ProviderContext): Promise<ProviderPlace | null>;
  autocomplete?(
    req: AutocompleteRequest,
    ctx: ProviderContext,
  ): Promise<ProviderPlace[]>;

  /** 경유지 간 길찾기. 결과 없으면 빈 배열(폴백 유도) */
  route?(req: RouteRequest, ctx: ProviderContext): Promise<ProviderRoute[]>;
  /** 원점×목적지 거리/시간 행렬 */
  distanceMatrix?(
    req: DistanceMatrixRequest,
    ctx: ProviderContext,
  ): Promise<ProviderDistanceMatrix>;
  /** 지점이 속한 지역의 인구통계. 커버 안 하면 null */
  demographics?(
    req: DemographicsRequest,
    ctx: ProviderContext,
  ): Promise<ProviderDemographics | null>;

  /** 선택적 상태 점검. 없으면 registry가 가벼운 기본 점검을 쓴다 */
  healthCheck?(ctx: ProviderContext): Promise<ProviderHealth>;
}

/** capability → 구현해야 하는 GeoProvider 메서드 이름 매핑 */
export const CAPABILITY_METHOD: Record<Capability, keyof GeoProvider> = {
  search: "searchPlaces",
  geocode: "geocode",
  reverseGeocode: "reverseGeocode",
  getPlace: "getPlace",
  autocomplete: "autocomplete",
  route: "route",
  distanceMatrix: "distanceMatrix",
  demographics: "demographics",
};
