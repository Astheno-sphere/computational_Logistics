import type { GeoProviderError, ProviderPlace } from "@geowirehq/provider-sdk";
import type {
  Capability,
  CountryCode,
  LatLng,
  RequestOptions,
  Strategy,
  SearchPlacesRequest,
  GeocodeRequest,
  ReverseGeocodeRequest,
  AutocompleteRequest,
} from "@geowirehq/schema";

/** ProviderPlace[] 를 반환하는 공급자 메서드 (getPlace 제외 — 단수 반환이라 별도 경로) */
export type ListMethod = "searchPlaces" | "geocode" | "reverseGeocode" | "autocomplete";

export type ListRequest =
  | SearchPlacesRequest
  | GeocodeRequest
  | ReverseGeocodeRequest
  | AutocompleteRequest;

/**
 * 파이프라인이 공급자에 위임할 단일 연산의 서술.
 * search/geocode/reverse/autocomplete를 하나의 plan→execute 경로로 통합한다.
 */
export interface OperationSpec {
  capability: Capability;
  method: ListMethod;
  request: ListRequest;
  /** 라우팅용 국가 (없으면 기본 라우팅) */
  country?: CountryCode;
  /** 거리 계산 기준점 (search near) */
  near?: LatLng;
  /** 반경 상한(m). 지정 시 near 기준 이 반경을 벗어난 결과를 제외한다 */
  radiusMeters?: number;
  /** 결과 상한 */
  limit?: number;
  options?: RequestOptions;
}

/** 단일 공급자 1회 호출의 결과 (성공/실패 무관하게 기록) */
export interface ProviderInvocation {
  id: string;
  ok: boolean;
  places: ProviderPlace[];
  latencyMs: number;
  /** ok=false일 때의 정규화된 에러 */
  error?: GeoProviderError;
  /** 회로 open 등으로 호출하지 않고 건너뛴 경우 — meta에서 skipped로 분류 */
  skipped?: boolean;
}

/** plan 단계의 산출물 */
export interface OperationPlan {
  strategy: Strategy;
  /** 호출 순서(우선순위)대로 정렬된 대상 공급자 id */
  providerIds: string[];
}
