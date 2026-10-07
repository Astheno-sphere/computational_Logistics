import type { ProviderPlace } from "@geowirehq/provider-sdk";
import type { LatLng, Place, PlaceSource } from "@geowirehq/schema";
import { makePlaceId } from "../ids.js";
import { haversineMeters } from "../geo.js";

/** 이 ProviderPlace가 값을 채운 Place 필드 경로 목록 (병합 provenance 추적: PlaceSource.fields) */
export function presentFields(pp: ProviderPlace): string[] {
  const fields: string[] = ["name", "location", "categories"];
  if (pp.localizedNames) fields.push("localizedNames");
  if (pp.address) fields.push("address");
  if (pp.contact) fields.push("contact");
  if (pp.business) fields.push("business");
  if (pp.metadata) fields.push("metadata");
  return fields;
}

/**
 * 공급자의 정규화 결과(ProviderPlace)를 통합 Place로 승격한다 (설계 §7.1 5단계 Normalize).
 * core의 책임인 필드를 채운다: 안정적 내부 `id`, `sources[]`(provenance), `distanceMeters`.
 * `attributions`는 빈 배열로 두고 Policy Engine(§8.2, M4)이 주입한다.
 */
export function toPlace(
  pp: ProviderPlace,
  providerId: string,
  nowMs: number,
  near?: LatLng,
): Place {
  const source: PlaceSource = {
    provider: providerId,
    providerPlaceId: pp.providerPlaceId,
    fetchedAt: new Date(nowMs).toISOString(),
    fields: presentFields(pp),
  };
  if (pp.confidence != null) source.confidence = pp.confidence;

  const place: Place = {
    id: makePlaceId(providerId, pp.providerPlaceId),
    name: pp.name,
    categories: pp.categories,
    location: pp.location,
    sources: [source],
    attributions: [],
  };
  if (pp.localizedNames) place.localizedNames = pp.localizedNames;
  if (pp.address) place.address = pp.address;
  if (pp.contact) place.contact = pp.contact;
  if (pp.business) place.business = pp.business;
  if (pp.metadata) place.metadata = pp.metadata;
  if (pp.confidence != null) place.confidence = pp.confidence;
  if (pp.distanceMeters != null) place.distanceMeters = pp.distanceMeters;
  else if (near) place.distanceMeters = haversineMeters(near, pp.location);

  return place;
}
