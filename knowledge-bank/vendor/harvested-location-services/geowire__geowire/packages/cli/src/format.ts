import type { Place, ResponseMeta } from "@geowirehq/schema";

/** 문자열을 최대 길이로 자르고 말줄임표 */
function truncate(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`;
}

/** 셀 배열들을 정렬된 표로 (열 폭 = 최댓값) */
function renderTable(headers: string[], rows: string[][]): string {
  const widths = headers.map((h, i) =>
    Math.max(h.length, ...rows.map((r) => (r[i] ?? "").length)),
  );
  const line = (cells: string[]): string =>
    cells.map((c, i) => (c ?? "").padEnd(widths[i]!)).join("  ").trimEnd();
  const sep = widths.map((w) => "─".repeat(w)).join("  ");
  return [line(headers), sep, ...rows.map(line)].join("\n");
}

/** 사용 공급자의 총 응답시간(최댓값 — 병렬 호출 기준) */
function totalLatency(meta: ResponseMeta): number {
  return meta.providersUsed.reduce((max, u) => Math.max(max, u.latencyMs), 0);
}

/**
 * 검색/지오코딩 결과를 터미널 표로 (README GIF 재료 — 출처·응답시간 포함).
 */
export function formatSearchTable(results: Place[], meta: ResponseMeta): string {
  const used = meta.providersUsed.map((u) => u.provider).join(", ") || "none";
  const header = `Found ${results.length} place${results.length === 1 ? "" : "s"} · ${meta.strategy} · ${used} · ${Math.round(totalLatency(meta))}ms`;

  if (results.length === 0) {
    const skipped = meta.providersSkipped.map((s) => `${s.provider}(${s.reason})`).join(", ");
    const note = skipped ? `\nSkipped: ${skipped}` : "";
    return `${header}${note}`;
  }

  const rows = results.map((p, i) => [
    String(i + 1),
    truncate(p.name, 28),
    p.distanceMeters != null ? `${Math.round(p.distanceMeters)}m` : "-",
    truncate(p.address?.formatted ?? "-", 40),
    p.sources.map((s) => s.provider).join(","),
  ]);

  const table = renderTable(["#", "Name", "Distance", "Address", "Sources"], rows);
  const parts = [header, "", table];
  if (meta.dedup) parts.push(`\ndedup: ${meta.dedup.before}→${meta.dedup.after}`);
  if (meta.estimatedCostUSD != null) parts.push(`est. cost: $${meta.estimatedCostUSD.toFixed(4)}`);
  if (meta.attributions.length) parts.push(`Attribution: ${meta.attributions.join("; ")}`);
  return parts.join("\n");
}

/** 단일 장소 상세를 사람이 읽기 좋은 블록으로 (`geowire get`용). */
export function formatPlace(p: Place): string {
  const lines: (string | undefined)[] = [
    p.name,
    p.address?.formatted ? `  ${p.address.formatted}` : undefined,
    `  (${p.location.latitude}, ${p.location.longitude})`,
    p.categories.length ? `  categories: ${p.categories.join(", ")}` : undefined,
    p.business?.openingHours ? `  hours: ${p.business.openingHours}` : undefined,
    p.business?.rating != null
      ? `  rating: ${p.business.rating}${p.business.priceLevel != null ? ` · price ${"$".repeat(p.business.priceLevel || 1)}` : ""}`
      : undefined,
    p.contact?.phone ? `  phone: ${p.contact.phone}` : undefined,
    p.contact?.website ? `  website: ${p.contact.website}` : undefined,
    `  sources: ${p.sources.map((s) => `${s.provider}:${s.providerPlaceId}`).join(", ")}`,
    p.attributions.length ? `  ${p.attributions.join("; ")}` : undefined,
  ];
  return lines.filter((l): l is string => l != null).join("\n");
}
