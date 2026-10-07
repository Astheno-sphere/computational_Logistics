import { defineProvider, GeoProviderError } from "@geowirehq/provider-sdk";
import type { GeoProvider, ProviderContext } from "@geowirehq/provider-sdk";
import type { ProviderManifest, ProviderErrorCode } from "@geowirehq/schema";
import type { ProviderPlace, ProviderRoute, ProviderDistanceMatrix } from "@geowirehq/provider-sdk";

/** 테스트용 최소 ProviderContext */
export function testContext(overrides: Partial<ProviderContext> = {}): ProviderContext {
  return {
    fetch: overrides.fetch ?? (async () => new Response("{}")),
    logger: overrides.logger ?? {
      debug() {},
      info() {},
      warn() {},
      error() {},
    },
    now: overrides.now ?? (() => 1_700_000_000_000),
    signal: overrides.signal,
  };
}

/** 최소 manifest 빌더 (undefined 필드는 기본값으로 대체) */
export function manifest(over: Partial<ProviderManifest> & { id: string }): ProviderManifest {
  const m: ProviderManifest = {
    id: over.id,
    name: over.name ?? over.id,
    capabilities: over.capabilities ?? ["search"],
    authType: over.authType ?? "none",
    policy: over.policy ?? { maxCacheTtlSeconds: 86_400, canStorePermanently: true },
  };
  if (over.coverage) m.coverage = over.coverage;
  if (over.cost) m.cost = over.cost;
  if (over.rateLimit) m.rateLimit = over.rateLimit;
  if (over.fieldAuthority) m.fieldAuthority = over.fieldAuthority;
  return m;
}

export interface FakeProviderSpec {
  id: string;
  name?: string;
  authType?: "apiKey" | "oauth" | "none";
  capabilities?: ProviderManifest["capabilities"];
  policy?: ProviderManifest["policy"];
  cost?: ProviderManifest["cost"];
  coverage?: ProviderManifest["coverage"];
  /** 역할 기반 필드 소싱 선언 (필드별 권위 가중) */
  fieldAuthority?: ProviderManifest["fieldAuthority"];
  /** 고정 검색 결과. 함수면 요청마다 계산 */
  search?: ProviderPlace[] | (() => ProviderPlace[]);
  /** route capability가 반환할 ProviderRoute 배열 */
  routeResult?: ProviderRoute[];
  /** distanceMatrix capability가 반환할 ProviderDistanceMatrix */
  matrixResult?: ProviderDistanceMatrix;
  /** 지정 시 searchPlaces가 이 코드로 GeoProviderError를 던진다 */
  failWith?: ProviderErrorCode;
  /** 응답 지연(ms) 시뮬레이션 — fastest 레이스 테스트용 */
  delayMs?: number;
  /** 호출 지연(ms) 시뮬레이션용 카운터 훅 */
  onCall?: () => void;
}

/** 정해진 결과/실패를 내는 가짜 provider (통합 테스트용).
 * 선언한 capability마다 동일한 결과/실패를 내는 메서드를 붙인다 — defineProvider의
 * capability↔메서드 일치 검사를 통과시키기 위함. */
export function fakeProvider(spec: FakeProviderSpec): GeoProvider {
  const caps = spec.capabilities ?? ["search"];
  const m = manifest({
    id: spec.id,
    name: spec.name,
    authType: spec.authType,
    capabilities: caps,
    policy: spec.policy,
    cost: spec.cost,
    coverage: spec.coverage,
    fieldAuthority: spec.fieldAuthority,
  });

  const run = async (): Promise<ProviderPlace[]> => {
    spec.onCall?.();
    if (spec.delayMs != null) await new Promise((r) => setTimeout(r, spec.delayMs));
    if (spec.failWith) {
      throw new GeoProviderError(spec.failWith, `${spec.id} failed with ${spec.failWith}`, {
        provider: spec.id,
      });
    }
    return typeof spec.search === "function" ? spec.search() : (spec.search ?? []);
  };

  const impl: Record<string, unknown> = { manifest: m };
  if (caps.includes("search")) impl.searchPlaces = async () => run();
  if (caps.includes("geocode")) impl.geocode = async () => run();
  if (caps.includes("reverseGeocode")) impl.reverseGeocode = async () => run();
  if (caps.includes("autocomplete")) impl.autocomplete = async () => run();
  if (caps.includes("getPlace")) impl.getPlace = async () => (await run())[0] ?? null;
  if (caps.includes("route"))
    impl.route = async () => {
      spec.onCall?.();
      if (spec.failWith) {
        throw new GeoProviderError(spec.failWith, `${spec.id} failed`, { provider: spec.id });
      }
      return spec.routeResult ?? [];
    };
  if (caps.includes("distanceMatrix"))
    impl.distanceMatrix = async () => {
      spec.onCall?.();
      if (spec.failWith) {
        throw new GeoProviderError(spec.failWith, `${spec.id} failed`, { provider: spec.id });
      }
      return spec.matrixResult ?? { rows: [] };
    };

  return defineProvider(impl as Parameters<typeof defineProvider>[0]);
}

/** ProviderPlace 빌더 — 필수 필드 최소로 */
export function place(over: Partial<ProviderPlace> & { providerPlaceId: string; name: string }): ProviderPlace {
  return {
    name: over.name,
    categories: over.categories ?? [],
    location: over.location ?? { latitude: 0, longitude: 0 },
    providerPlaceId: over.providerPlaceId,
    ...over,
  };
}

/** 단일 소스를 가진 완전한 Place 빌더 (dedup/merge/rank 단위 테스트용) */
export function builtPlace(args: {
  provider: string;
  providerPlaceId: string;
  name: string;
  location?: { latitude: number; longitude: number };
  categories?: string[];
  address?: import("@geowirehq/schema").Address;
  contact?: import("@geowirehq/schema").Contact;
  business?: import("@geowirehq/schema").Business;
  confidence?: number;
  distanceMeters?: number;
  fetchedAt?: string;
}): import("@geowirehq/schema").Place {
  const source: import("@geowirehq/schema").PlaceSource = {
    provider: args.provider,
    providerPlaceId: args.providerPlaceId,
    fetchedAt: args.fetchedAt ?? "2026-07-17T00:00:00.000Z",
  };
  if (args.confidence != null) source.confidence = args.confidence;
  const p: import("@geowirehq/schema").Place = {
    id: `gwp_${args.provider}_${args.providerPlaceId}`,
    name: args.name,
    categories: args.categories ?? [],
    location: args.location ?? { latitude: 0, longitude: 0 },
    sources: [source],
    attributions: [],
  };
  if (args.address) p.address = args.address;
  if (args.contact) p.contact = args.contact;
  if (args.business) p.business = args.business;
  if (args.confidence != null) p.confidence = args.confidence;
  if (args.distanceMeters != null) p.distanceMeters = args.distanceMeters;
  return p;
}
