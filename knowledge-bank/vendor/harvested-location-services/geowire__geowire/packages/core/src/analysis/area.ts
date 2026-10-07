import type {
  AreaInsightsRequest,
  AreaInsights,
  CategoryInsight,
  StatSummary,
  Place,
  ResponseMeta,
  ProviderUsage,
  ProviderSkip,
} from "@geowirehq/schema";
import { runOperation } from "../pipeline/pipeline.js";
import { runDemographics } from "../pipeline/routing.js";
import { resolveCountry } from "../pipeline/normalize-request.js";
import type { OperationSpec } from "../pipeline/types.js";
import type { PipelineHost } from "../pipeline/pipeline.js";

const ACTIVITY_NOTE =
  "proxy from Foursquare popularity + review counts — not measured foot-traffic";

/** 수치 배열 → 요약 통계(개수·평균·최소·최대). 표본 없으면 undefined */
function summarize(values: number[]): StatSummary | undefined {
  if (values.length === 0) return undefined;
  const sum = values.reduce((a, b) => a + b, 0);
  return {
    count: values.length,
    average: Math.round((sum / values.length) * 100) / 100,
    min: Math.min(...values),
    max: Math.max(...values),
  };
}

/** 원의 면적(제곱킬로미터). r은 미터 */
function areaSqKm(radiusMeters: number): number {
  const rKm = radiusMeters / 1000;
  return Math.round(Math.PI * rKm * rKm * 1000) / 1000;
}

/** 평점 우선(내림차순), 없으면 거리 오름차순으로 대표 장소 선정 */
function topPlaces(places: Place[], n: number): Place[] {
  return [...places]
    .sort((a, b) => {
      const ra = a.business?.rating ?? -1;
      const rb = b.business?.rating ?? -1;
      if (rb !== ra) return rb - ra;
      return (a.distanceMeters ?? Infinity) - (b.distanceMeters ?? Infinity);
    })
    .slice(0, n);
}

/** 여러 검색 meta를 하나로 합친다(공급자 합집합, 비용 합산) */
function combineMeta(metas: ResponseMeta[]): ResponseMeta {
  const usedByProvider = new Map<string, ProviderUsage>();
  const skipped = new Map<string, ProviderSkip>();
  const failed = new Map<string, ProviderSkip>();
  const attributions = new Set<string>();
  let cost = 0;
  for (const m of metas) {
    for (const u of m.providersUsed) {
      const prev = usedByProvider.get(u.provider);
      if (prev) {
        prev.resultCount += u.resultCount;
        prev.latencyMs = Math.max(prev.latencyMs, u.latencyMs);
      } else usedByProvider.set(u.provider, { ...u });
    }
    for (const s of m.providersSkipped) skipped.set(s.provider, s);
    for (const f of m.providersFailed) failed.set(f.provider, f);
    for (const a of m.attributions) attributions.add(a);
    if (m.estimatedCostUSD) cost += m.estimatedCostUSD;
  }
  const meta: ResponseMeta = {
    providersUsed: [...usedByProvider.values()],
    providersSkipped: [...skipped.values()],
    providersFailed: [...failed.values()],
    strategy: "merge",
    attributions: [...attributions],
  };
  if (cost > 0) meta.estimatedCostUSD = Math.round(cost * 1e6) / 1e6;
  return meta;
}

/**
 * 지역/상권 분석 (설계: analysis/v1).
 * 업종마다 중심점 반경 검색을 돌려(merge 전략으로 공급자 병합·중복제거) 밀도·경쟁·평점 지형을 집계한다.
 * 상위 레이어라 새 provider가 필요 없다 — 검색 파이프라인 위에 쌓는다.
 */
export async function runAreaInsights(
  host: PipelineHost,
  req: AreaInsightsRequest,
): Promise<{ insights: AreaInsights; meta: ResponseMeta }> {
  const country = resolveCountry(undefined, req.center);
  const area = areaSqKm(req.radiusMeters);
  const metas: ResponseMeta[] = [];
  const categories: CategoryInsight[] = [];
  const seen = new Map<string, Place>(); // 전 업종 합산 중복제거(place.id 기준)

  for (const category of req.categories) {
    const spec: OperationSpec = {
      capability: "search",
      method: "searchPlaces",
      request: {
        query: category,
        near: req.center,
        radiusMeters: req.radiusMeters,
        limit: req.limitPerCategory,
        options: { ...req.options, strategy: req.options?.strategy ?? "merge" },
      },
      country,
      near: req.center,
      radiusMeters: req.radiusMeters,
      limit: req.limitPerCategory,
      options: { ...req.options, strategy: req.options?.strategy ?? "merge" },
    };
    const { results, meta } = await runOperation(host, spec);
    metas.push(meta);
    for (const p of results) if (!seen.has(p.id)) seen.set(p.id, p);

    const ratings = results
      .map((p) => p.business?.rating)
      .filter((r): r is number => typeof r === "number");
    const prices = results
      .map((p) => p.business?.priceLevel)
      .filter((v): v is number => typeof v === "number");

    const insight: CategoryInsight = {
      category,
      count: results.length,
      densityPerSqKm: Math.round((results.length / area) * 100) / 100,
      topPlaces: topPlaces(results, 3),
    };
    const r = summarize(ratings);
    if (r) insight.rating = r;
    const pr = summarize(prices);
    if (pr) insight.priceLevel = pr;

    // 활동/유동인구 프록시: popularity 평균 + 리뷰 수 합계 (실측 아님)
    const pops = results
      .map((p) => p.business?.popularity)
      .filter((v): v is number => typeof v === "number");
    const totalReviews = results.reduce((s, p) => s + (p.business?.reviewCount ?? 0), 0);
    if (pops.length > 0 || totalReviews > 0) {
      const activity: NonNullable<CategoryInsight["activity"]> = {
        totalReviews,
        note: ACTIVITY_NOTE,
      };
      if (pops.length > 0) {
        activity.avgPopularity = Math.round((pops.reduce((a, b) => a + b, 0) / pops.length) * 100) / 100;
      }
      insight.activity = activity;
    }
    categories.push(insight);
  }

  const allPlaces = [...seen.values()];
  const overallRatings = allPlaces
    .map((p) => p.business?.rating)
    .filter((r): r is number => typeof r === "number");

  const insights: AreaInsights = {
    center: req.center,
    radiusMeters: req.radiusMeters,
    areaSqKm: area,
    totalPlaces: allPlaces.length,
    densityPerSqKm: Math.round((allPlaces.length / area) * 100) / 100,
    categories,
  };
  const overall = summarize(overallRatings);
  if (overall) insights.rating = overall;

  // 중심점 인구통계(있으면). demographics 공급자가 없거나 지역 미커버면 조용히 생략.
  try {
    const { profile, meta } = await runDemographics(host, {
      location: req.center,
      options: req.options,
    });
    metas.push(meta);
    if (profile) insights.demographics = profile;
  } catch {
    // 인구통계는 부가 정보 — 실패해도 상권 분석은 그대로 낸다
  }

  return { insights, meta: combineMeta(metas) };
}
