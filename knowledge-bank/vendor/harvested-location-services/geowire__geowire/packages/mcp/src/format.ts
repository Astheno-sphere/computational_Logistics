import type {
  Place,
  ResponseMeta,
  Route,
  DistanceMatrix,
  AreaInsights,
  DemographicProfile,
  Isochrone,
} from "@geowirehq/schema";
import type { ProviderInfo } from "@geowirehq/core";

/** 인구통계 프로파일을 한두 줄 요약으로 */
function summarizeDemographics(d: DemographicProfile): string {
  const bits: string[] = [];
  if (d.population != null) bits.push(`pop ${d.population.toLocaleString()}`);
  if (d.populationDensityPerSqKm != null) bits.push(`${d.populationDensityPerSqKm}/km²`);
  if (d.medianAgeYears != null) bits.push(`median age ${d.medianAgeYears}`);
  if (d.medianHouseholdIncome) bits.push(`median income ${d.medianHouseholdIncome.amount.toLocaleString()} ${d.medianHouseholdIncome.currency}`);
  if (d.households != null) bits.push(`${d.households.toLocaleString()} households`);
  if (d.avgHouseholdSize != null) bits.push(`avg ${d.avgHouseholdSize}/household`);
  return `${d.areaName} (${d.areaLevel}): ${bits.join(", ")}`;
}

/** 초 → 사람이 읽는 시간 (예: "1h 12m", "8m", "45s") */
function humanDuration(seconds: number): string {
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

/** 미터 → 사람이 읽는 거리 (예: "12.4 km", "850 m") */
function humanDistance(meters: number): string {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}

/** 좌표를 소수점 5자리로 (약 1m 정밀도) */
function coord(n: number): string {
  return n.toFixed(5);
}

/** Place 한 건을 한 줄 요약으로 */
function formatPlace(place: Place, index?: number): string {
  const prefix = index != null ? `${index + 1}. ` : "";
  const parts: string[] = [`${prefix}${place.name}`];
  if (place.address?.formatted) parts.push(place.address.formatted);
  parts.push(`(${coord(place.location.latitude)}, ${coord(place.location.longitude)})`);
  const extras: string[] = [];
  if (place.distanceMeters != null) extras.push(`${Math.round(place.distanceMeters)}m away`);
  if (place.contact?.phone) extras.push(place.contact.phone);
  if (place.business?.openingHours) extras.push(place.business.openingHours);
  if (place.business?.rating != null) {
    extras.push(`★${place.business.rating}${place.business.reviewCount != null ? ` (${place.business.reviewCount})` : ""}`);
  }
  const sources = place.sources.map((s) => `${s.provider}:${s.providerPlaceId}`).join(", ");
  extras.push(`sources: ${sources}`);
  return `${parts.join(" — ")}\n   ${extras.join(" · ")}`;
}

/** meta의 투명성 정보를 한 줄로 (사용/스킵/실패/전략/비용) */
function formatMeta(meta: ResponseMeta): string {
  const bits: string[] = [`strategy: ${meta.strategy}`];
  if (meta.providersUsed.length) bits.push(`used: ${meta.providersUsed.map((u) => u.provider).join(", ")}`);
  if (meta.providersSkipped.length)
    bits.push(`skipped: ${meta.providersSkipped.map((s) => `${s.provider}(${s.reason})`).join(", ")}`);
  if (meta.providersFailed.length)
    bits.push(`failed: ${meta.providersFailed.map((s) => `${s.provider}(${s.reason})`).join(", ")}`);
  if (meta.dedup) bits.push(`dedup: ${meta.dedup.before}→${meta.dedup.after}`);
  if (meta.estimatedCostUSD != null) bits.push(`est. cost: $${meta.estimatedCostUSD.toFixed(4)}`);
  if (meta.cache?.hit) bits.push("cache: hit");
  return bits.join(" | ");
}

/** 검색/지오코딩 결과를 사람이 읽는 요약 텍스트로 */
export function formatResults(results: Place[], meta: ResponseMeta): string {
  const header =
    results.length === 0
      ? "No places found."
      : `Found ${results.length} place${results.length === 1 ? "" : "s"}:`;
  const body = results.map((p, i) => formatPlace(p, i)).join("\n");
  const footer = formatMeta(meta);
  const attribution = meta.attributions.length ? `\nAttribution: ${meta.attributions.join("; ")}` : "";
  return `${header}\n${body}\n\n${footer}${attribution}`.trim();
}

/** get_place 단일 결과 텍스트 */
export function formatSinglePlace(place: Place | null, id: string): string {
  if (!place) {
    return `No place found for id "${id}". Use a provider reference like "google:ChIJ..." or "nominatim:node/123" (from a search result's sources).`;
  }
  const attribution = place.attributions.length ? `\nAttribution: ${place.attributions.join("; ")}` : "";
  return `${formatPlace(place)}${attribution}`;
}

/** 길찾기 결과 텍스트 */
export function formatRoutes(routes: Route[], meta: ResponseMeta): string {
  if (routes.length === 0) {
    return `No route found.\n\n${formatMeta(meta)}`;
  }
  const lines = routes.map((r, i) => {
    const label = routes.length > 1 ? `Route ${i + 1}: ` : "Route: ";
    const legs =
      r.legs.length > 1
        ? `\n   legs: ${r.legs.map((l) => `${humanDistance(l.distanceMeters)}/${humanDuration(l.durationSeconds)}`).join(" → ")}`
        : "";
    return `${label}${humanDistance(r.distanceMeters)}, ${humanDuration(r.durationSeconds)} (${r.provider})${legs}`;
  });
  const attribution = meta.attributions.length ? `\nAttribution: ${meta.attributions.join("; ")}` : "";
  return `${lines.join("\n")}\n\n${formatMeta(meta)}${attribution}`.trim();
}

/** 거리 행렬 텍스트 (작은 행렬은 표, 큰 건 요약) */
export function formatMatrix(matrix: DistanceMatrix, meta: ResponseMeta): string {
  const rows = matrix.rows.map((row, i) => {
    const cells = row.map((c, j) => {
      if (c.durationSeconds == null && c.distanceMeters == null) return `[${i}][${j}] —`;
      const dist = c.distanceMeters != null ? humanDistance(c.distanceMeters) : "?";
      const dur = c.durationSeconds != null ? humanDuration(c.durationSeconds) : "?";
      return `[${i}→${j}] ${dist}/${dur}`;
    });
    return cells.join("  ");
  });
  const attribution = meta.attributions.length ? `\nAttribution: ${meta.attributions.join("; ")}` : "";
  return `Distance matrix (${matrix.rows.length}×${matrix.rows[0]?.length ?? 0}, ${matrix.provider}):\n${rows.join("\n")}\n\n${formatMeta(meta)}${attribution}`.trim();
}

/** 지역/상권 분석 텍스트 */
export function formatAreaInsights(insights: AreaInsights, meta: ResponseMeta): string {
  const head = `Area analysis — ${insights.radiusMeters}m radius (${insights.areaSqKm} km²), ${insights.totalPlaces} places, ${insights.densityPerSqKm}/km²`;
  const rows = insights.categories.map((c) => {
    const rating = c.rating ? `, ★${c.rating.average} avg (${c.rating.count})` : "";
    const price = c.priceLevel ? `, price ${c.priceLevel.average.toFixed(1)}/4` : "";
    const top = c.topPlaces
      .map((p) => `${p.name}${p.business?.rating != null ? ` ★${p.business.rating}` : ""}`)
      .join(", ");
    return `- ${c.category}: ${c.count} found (${c.densityPerSqKm}/km²)${rating}${price}${top ? `\n    top: ${top}` : ""}`;
  });
  const overall = insights.rating ? `\nOverall rating: ★${insights.rating.average} avg over ${insights.rating.count} rated places` : "";
  const demo = insights.demographics ? `\nDemographics: ${summarizeDemographics(insights.demographics)}` : "";
  const attribution = meta.attributions.length ? `\nAttribution: ${meta.attributions.join("; ")}` : "";
  return `${head}\n${rows.join("\n")}${overall}${demo}\n\n${formatMeta(meta)}${attribution}`.trim();
}

/** get_demographics 텍스트 */
export function formatDemographics(profile: DemographicProfile | null, meta: ResponseMeta): string {
  if (!profile) {
    return `No demographics available for this location (needs a demographics provider covering the area — e.g. US Census with a free key, US only).\n\n${formatMeta(meta)}`;
  }
  const attribution = profile.attributions.length ? `\nAttribution: ${profile.attributions.join("; ")}` : "";
  return `${summarizeDemographics(profile)}${attribution}`;
}

/** 도달권(isochrone) 텍스트 */
export function formatIsochrone(iso: Isochrone | null, meta: ResponseMeta): string {
  if (!iso) {
    return `No isochrone available (needs a distance-matrix provider, e.g. OSRM — enabled by default).\n\n${formatMeta(meta)}`;
  }
  const ring = iso.polygon.coordinates[0]?.length ?? 0;
  const attribution = iso.attributions.length ? `\nAttribution: ${iso.attributions.join("; ")}` : "";
  return (
    `${iso.minutes}-min ${iso.mode} isochrone from (${coord(iso.origin.latitude)}, ${coord(iso.origin.longitude)}): ` +
    `~${iso.areaSqKm} km² reachable (${ring - 1}-point polygon, ${iso.reachableSamples}/${iso.sampleCount} samples in budget, ${iso.provider})\n` +
    `${iso.note}\n\n${formatMeta(meta)}${attribution}`
  );
}

/** list_geo_providers 텍스트 */
export function formatProviders(providers: ProviderInfo[]): string {
  if (providers.length === 0) return "No geo providers configured.";
  const lines = providers.map((p) => {
    const state = p.enabled ? "enabled" : "disabled";
    const attribution = p.attributionRequired ? ` · attribution: ${p.attributionRequired}` : "";
    return `- ${p.id} (${p.name}) — ${state}, auth: ${p.authType}, priority: ${p.priority}, capabilities: ${p.capabilities.join(", ")}${attribution}`;
  });
  return `${providers.length} provider(s):\n${lines.join("\n")}`;
}
