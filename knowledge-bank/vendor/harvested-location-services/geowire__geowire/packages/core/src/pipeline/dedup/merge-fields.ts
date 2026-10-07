import type { Business, Place, PlaceSource } from "@geowirehq/schema";
import { makePlaceId } from "../../ids.js";

/**
 * 필드별 공급자 강점 폴백 (설계 §7.3 "영업시간은 Google, 좌표는 OSM").
 * 앞에 있을수록 강하다. **주 소싱은 이제 provider manifest의 `fieldAuthority`가 담당**하며
 * (역할 기반 필드 소싱), 이 정적 테이블은 manifest 권위를 얻을 수 없을 때의 폴백이다.
 * 여기에도 없는 필드는 provider priority → source confidence 순으로 결정된다.
 */
export const DEFAULT_FIELD_STRENGTH: Record<string, string[]> = {
  location: ["nominatim", "osm"],
  address: ["google", "nominatim", "osm"],
  business: ["google"],
  contact: ["google"],
};

export interface MergeContext {
  /** provider id → 우선순위(높을수록 우선). config priority 기반 */
  providerRank: (providerId: string) => number;
  /**
   * 역할 기반 필드 소싱: provider가 manifest에 선언한 필드 권위(클수록 강함).
   * pipeline이 registry manifest에서 주입한다. undefined면 정적 폴백을 쓴다.
   */
  fieldAuthority?: (providerId: string, field: string) => number | undefined;
  fieldStrength?: Record<string, string[]>;
}

/** 특정 필드에 대한 place의 우선순위 점수 (클수록 우선) */
function fieldRank(field: string, place: Place, ctx: MergeContext): number {
  const provider = place.sources[0]!.provider;
  // 1순위: manifest가 선언한 필드 권위(역할 기반 소싱). 공급자가 스스로 역할을 밝힌다.
  const authority = ctx.fieldAuthority?.(provider, field);
  let strengthScore: number;
  if (authority != null && authority > 0) {
    strengthScore = authority * 1_000_000;
  } else {
    // 폴백: 정적 강점 테이블(manifest 권위 미선언 시 하위 호환)
    const strength = (ctx.fieldStrength ?? DEFAULT_FIELD_STRENGTH)[field];
    const idx = strength ? strength.indexOf(provider) : -1;
    strengthScore = idx >= 0 ? (strength!.length - idx) * 1_000_000 : 0;
  }
  // 강점이 최우선(큰 가중), 그다음 provider priority, 마지막으로 source confidence
  const conf = place.sources[0]!.confidence ?? 0;
  return strengthScore + ctx.providerRank(provider) * 1000 + conf;
}

/** place가 field 필드를 기여했다고 provenance에 기록한다 (sources[].fields의 근거) */
function contribute(place: Place, field: string, contributions: Map<string, Set<string>>): void {
  const src = place.sources[0]!;
  const key = `${src.provider}:${src.providerPlaceId}`;
  (contributions.get(key) ?? contributions.set(key, new Set()).get(key)!).add(field);
}

/** field 값을 가진 place 중 우선순위 최고를 고르고, 기여 provenance를 기록한다 */
function pick<T>(
  field: string,
  cluster: Place[],
  ctx: MergeContext,
  get: (p: Place) => T | undefined,
  contributions: Map<string, Set<string>>,
): T | undefined {
  const candidates = cluster.filter((p) => get(p) !== undefined);
  if (candidates.length === 0) return undefined;
  const winner = candidates.reduce((best, p) =>
    fieldRank(field, p, ctx) > fieldRank(field, best, ctx) ? p : best,
  );
  contribute(winner, field, contributions);
  return get(winner);
}

/**
 * business는 하위 필드마다 강점이 갈린다(역할 소싱: Google=리뷰, Foursquare=사진).
 * business 권위 승자의 스칼라(rating·영업시간·가격·리뷰수)를 기반으로 하되,
 * `reviews`는 승자에 없으면 권위 순으로 보강하고 `photos`는 전 소스 합집합으로 합쳐
 * "리뷰는 Google, 사진은 Foursquare"가 한 레코드에 **공존**하게 한다.
 */
function mergeBusiness(
  cluster: Place[],
  ctx: MergeContext,
  contributions: Map<string, Set<string>>,
): Business | undefined {
  const withBiz = cluster.filter((p) => p.business !== undefined);
  if (withBiz.length === 0) return undefined;
  // business 권위 내림차순 (동점이면 원래 순서 유지)
  const ranked = [...withBiz].sort(
    (a, b) => fieldRank("business", b, ctx) - fieldRank("business", a, ctx),
  );
  const merged: Business = { ...ranked[0]!.business! };
  contribute(ranked[0]!, "business", contributions);

  // reviews: 승자에 없으면 권위 순으로 처음 리뷰를 가진 소스에서 가져온다
  if (!merged.reviews?.length) {
    const r = ranked.find((p) => p.business?.reviews?.length);
    if (r) {
      merged.reviews = r.business!.reviews;
      contribute(r, "business", contributions);
    }
  }
  // photos: 모든 소스의 사진 합집합(중복 URL 제거, 권위 순)
  const photos: string[] = [];
  for (const p of ranked) {
    for (const url of p.business?.photos ?? []) {
      if (!photos.includes(url)) {
        photos.push(url);
        contribute(p, "business", contributions);
      }
    }
  }
  if (photos.length > 0) merged.photos = photos;
  else delete merged.photos;

  return merged;
}

/** 클러스터의 안정적 대표 소스(정렬 최소)로 내부 ID를 만든다 — 병합 후에도 불변 */
function clusterId(cluster: Place[]): string {
  const sorted = cluster
    .map((p) => p.sources[0]!)
    .sort((a, b) =>
      a.provider.localeCompare(b.provider) || a.providerPlaceId.localeCompare(b.providerPlaceId),
    );
  const rep = sorted[0]!;
  return makePlaceId(rep.provider, rep.providerPlaceId);
}

/** 종합 신뢰도: 최고 source confidence + 다중 소스 보너스(교차 확인) */
function mergedConfidence(sources: PlaceSource[]): number | undefined {
  const confs = sources.map((s) => s.confidence).filter((c): c is number => c != null);
  if (confs.length === 0) return undefined;
  const base = Math.max(...confs);
  return sources.length > 1 ? Math.min(1, base + 0.05 * (sources.length - 1)) : base;
}

/**
 * 동일 장소로 판정된 클러스터를 하나의 Place로 병합한다 (설계 §7.3).
 * 필드마다 가장 신뢰할 소스의 값을 취하고, 어느 소스가 어느 필드를 기여했는지
 * `sources[].fields`에 기록한다("영업시간은 google, 좌표는 osm"의 근거).
 * 단일 원소 클러스터는 그대로 반환한다.
 */
export function mergeCluster(cluster: Place[], ctx: MergeContext): Place {
  if (cluster.length === 1) return cluster[0]!;

  const contributions = new Map<string, Set<string>>();

  const name = pick("name", cluster, ctx, (p) => p.name, contributions)!;
  const location = pick("location", cluster, ctx, (p) => p.location, contributions)!;
  const address = pick("address", cluster, ctx, (p) => p.address, contributions);
  const contact = pick("contact", cluster, ctx, (p) => p.contact, contributions);
  const business = mergeBusiness(cluster, ctx, contributions);

  // categories·localizedNames는 합집합(정보 손실 방지)
  const categories = [...new Set(cluster.flatMap((p) => p.categories))];
  const localizedNames: Record<string, string> = {};
  for (const p of cluster) {
    if (p.localizedNames) Object.assign(localizedNames, p.localizedNames);
  }

  // 소스 합치기 + provenance(fields) 재기록
  const sources: PlaceSource[] = cluster.map((p) => {
    const src = p.sources[0]!;
    const key = `${src.provider}:${src.providerPlaceId}`;
    const fields = contributions.get(key);
    return { ...src, fields: fields ? [...fields] : [] };
  });

  const distances = cluster
    .map((p) => p.distanceMeters)
    .filter((d): d is number => d != null);

  const merged: Place = {
    id: clusterId(cluster),
    name,
    categories,
    location,
    sources,
    attributions: [],
  };
  if (Object.keys(localizedNames).length > 0) merged.localizedNames = localizedNames;
  if (address) merged.address = address;
  if (contact) merged.contact = contact;
  if (business) merged.business = business;
  if (distances.length > 0) merged.distanceMeters = Math.min(...distances);
  const confidence = mergedConfidence(sources);
  if (confidence != null) merged.confidence = confidence;

  return merged;
}
