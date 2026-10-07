import { z } from "zod";
import { Place, Route, DistanceMatrix, DemographicProfile } from "@geowirehq/schema";

/**
 * 공급자가 반환하는 정규화된 장소 — `Place`에서 **core의 책임인 필드를 제거**한 형태다.
 * 제거: `id`(내부 gwp_ ID 발급), `attributions`(Policy Engine 주입),
 * `confidence`(병합 후 종합 신뢰도), `sources`(core가 providerPlaceId로 구성).
 * 추가: 단수 `providerPlaceId` + 이 결과에 대한 공급자 자체 `confidence`(→ PlaceSource.confidence).
 *
 * `Place`에서 파생하므로 스키마가 바뀌면 자동으로 따라간다 (단일 진실원).
 */
export const ProviderPlace = Place.omit({
  id: true,
  sources: true,
  attributions: true,
  confidence: true,
}).extend({
  /** 공급자의 안정적 장소 식별자 (예: OSM "node/123", Google "ChIJ...") */
  providerPlaceId: z.string().min(1),
  /** 이 결과에 대한 공급자 자체 신뢰도 0~1 (병합 시 PlaceSource.confidence로 승격) */
  confidence: z.number().min(0).max(1).optional(),
});
export type ProviderPlace = z.infer<typeof ProviderPlace>;

/**
 * 공급자가 반환하는 경로 — `Route`에서 core가 채우는 `provider`·`attributions`를 제거한 형태.
 * `Route`에서 파생하므로 스키마 변경이 자동 반영된다(단일 진실원).
 */
export const ProviderRoute = Route.omit({ provider: true, attributions: true });
export type ProviderRoute = z.infer<typeof ProviderRoute>;

/** 공급자가 반환하는 거리 행렬 — `provider`·`attributions`는 core가 주입 */
export const ProviderDistanceMatrix = DistanceMatrix.omit({
  provider: true,
  attributions: true,
});
export type ProviderDistanceMatrix = z.infer<typeof ProviderDistanceMatrix>;

/** 공급자가 반환하는 인구통계 — `attributions`는 core가 주입(공급자는 source만 채움) */
export const ProviderDemographics = DemographicProfile.omit({ attributions: true });
export type ProviderDemographics = z.infer<typeof ProviderDemographics>;

/** 공급자 상태 점검 결과 (registry의 서킷브레이커·`/v1/providers` 노출용) */
export interface ProviderHealth {
  ok: boolean;
  /** 점검 왕복 시간(ms) */
  latencyMs?: number;
  /** ok=false일 때 사람이 읽는 사유 */
  detail?: string;
}
