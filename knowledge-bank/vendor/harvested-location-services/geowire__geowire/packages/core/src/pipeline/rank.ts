import type { LatLng, Place } from "@geowirehq/schema";
import type { RankWeights } from "../config/schema.js";

export interface RankOptions {
  weights: RankWeights;
  /** 거리 신호 기준점. 없으면 거리 신호는 비활성(가중치 재정규화) */
  near?: LatLng;
  /** 최신성 신호 기준 현재 시각(epoch ms) */
  nowMs: number;
}

/** 거리 신호(0~1): 가까울수록 1. 500m에서 0.5, 완만한 감쇠 */
function distanceScore(place: Place): number | undefined {
  if (place.distanceMeters == null) return undefined;
  return 1 / (1 + place.distanceMeters / 500);
}

/** 영업시간 신뢰 신호: openingHours 정보가 있으면 1, 없으면 0 */
function openingHoursScore(place: Place): number {
  return place.business?.openingHours ? 1 : 0;
}

/** 공급자 신뢰 신호: 종합/최대 source confidence, 없으면 중립 0.5 */
function confidenceScore(place: Place): number {
  if (place.confidence != null) return place.confidence;
  const confs = place.sources.map((s) => s.confidence).filter((c): c is number => c != null);
  return confs.length > 0 ? Math.max(...confs) : 0.5;
}

/** 최신성 신호(0~1): 방금 가져왔을수록 1. 1시간 age에서 0.5 */
function freshnessScore(place: Place, nowMs: number): number {
  const times = place.sources.map((s) => Date.parse(s.fetchedAt)).filter((t) => !Number.isNaN(t));
  if (times.length === 0) return 0.5;
  const ageHours = Math.max(0, (nowMs - Math.max(...times)) / 3_600_000);
  return 1 / (1 + ageHours);
}

/**
 * 랭킹 점수(0~1). 거리40/영업시간25/공급자신뢰20/최신성15 가중합(설계 §7.4, 설정 가능).
 * 거리 신호가 없으면(near 미지정) 해당 가중치를 빼고 재정규화한다.
 */
export function rankScore(place: Place, opts: RankOptions): number {
  const w = opts.weights;
  let sum = 0;
  let active = 0;

  const dist = distanceScore(place);
  if (dist != null) {
    sum += w.distance * dist;
    active += w.distance;
  }
  sum += w.openingHours * openingHoursScore(place);
  active += w.openingHours;
  sum += w.providerConfidence * confidenceScore(place);
  active += w.providerConfidence;
  sum += w.freshness * freshnessScore(place, opts.nowMs);
  active += w.freshness;

  return active === 0 ? 0 : sum / active;
}

/**
 * 랭킹 점수 내림차순으로 정렬한다(설계 §7.4). 원본을 변경하지 않는 안정 정렬.
 * 동점은 입력 순서(= provider 우선순위·dedup 순서)를 보존한다.
 */
export function rankPlaces(places: Place[], opts: RankOptions): Place[] {
  return places
    .map((place, index) => ({ place, index, score: rankScore(place, opts) }))
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map((x) => x.place);
}
