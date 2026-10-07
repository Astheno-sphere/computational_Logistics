import { describe, expect, it } from "vitest";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  defineProvider,
  errorFromHttpStatus,
  type GeoProvider,
} from "@geowirehq/provider-sdk";
import {
  runConformanceChecks,
  runConformanceTests,
  loadFixture,
  recordFixture,
  type CapabilityFixture,
} from "../src/index.js";

/** HTTP 기반 레퍼런스 공급자 — 정상 구현이면 전 항목을 통과해야 한다 */
const reference = defineProvider({
  manifest: {
    id: "ref",
    name: "Reference Provider",
    capabilities: ["search"],
    authType: "none",
    policy: {
      maxCacheTtlSeconds: 3600,
      canStorePermanently: true,
      attributionRequired: "© Reference",
    },
  },
  async searchPlaces(_req, ctx) {
    const res = await ctx.fetch("https://api.ref.test/search");
    if (!res.ok) throw errorFromHttpStatus(res.status, { provider: "ref" });
    const body = (await res.json()) as {
      places: Array<{
        id: string;
        name: string;
        categories?: string[];
        location: { latitude: number; longitude: number };
      }>;
    };
    return body.places.map((p) => ({
      providerPlaceId: p.id,
      name: p.name,
      categories: p.categories ?? [],
      location: p.location,
    }));
  },
});

const searchFixture: CapabilityFixture = {
  request: { query: "pharmacy", limit: 5 },
  responseBody: {
    places: [
      {
        id: "node/1",
        name: "Pharmacity",
        categories: ["pharmacy"],
        location: { latitude: 10.78, longitude: 106.69 },
      },
    ],
  },
  minResults: 1,
};

// 레퍼런스 공급자가 vitest 바인딩으로 전 항목 통과하는지 실제로 등록·실행 (DoD)
runConformanceTests(reference, { fixtures: { search: searchFixture } });

describe("runConformanceChecks", () => {
  it("passes every check for a correct HTTP provider", async () => {
    const results = await runConformanceChecks(reference, {
      fixtures: { search: searchFixture },
    });
    const failures = results.filter((r) => !r.passed);
    expect(failures, JSON.stringify(failures, null, 2)).toHaveLength(0);
    // 6개 축이 모두 평가됐는지 (manifest, capability, fixture, 500, 401, timeout, attribution)
    expect(results.length).toBeGreaterThanOrEqual(7);
  });

  it("flags a provider that returns an invalid ProviderPlace", async () => {
    const broken: GeoProvider = defineProvider({
      manifest: reference.manifest,
      async searchPlaces() {
        // name 누락 → ProviderPlace 스키마 위반
        return [{ providerPlaceId: "x", categories: [], location: { latitude: 0, longitude: 0 } } as never];
      },
    });
    const results = await runConformanceChecks(broken, {
      fixtures: { search: searchFixture },
    });
    const fixtureCheck = results.find((r) => r.name.startsWith("fixture:search"));
    expect(fixtureCheck?.passed).toBe(false);
    expect(fixtureCheck?.detail).toContain("invalid ProviderPlace");
  });

  it("flags a declared capability with no implementation", async () => {
    const missing = {
      manifest: {
        id: "missing",
        name: "Missing Method",
        capabilities: ["geocode"],
        authType: "none",
        policy: { maxCacheTtlSeconds: null, canStorePermanently: false },
      },
    } as unknown as GeoProvider;
    const results = await runConformanceChecks(missing);
    const capCheck = results.find((r) => r.name === "declared capabilities are implemented");
    expect(capCheck?.passed).toBe(false);
    expect(capCheck?.detail).toContain("geocode");
  });

  it("flags a provider that does not normalize HTTP errors", async () => {
    const swallowsErrors: GeoProvider = defineProvider({
      manifest: reference.manifest,
      async searchPlaces() {
        // fetch 결과를 무시하고 항상 빈 배열 → 500/401/timeout에서도 throw하지 않음
        return [];
      },
    });
    const results = await runConformanceChecks(swallowsErrors, {
      fixtures: { search: { ...searchFixture, minResults: 0 } },
    });
    const errorCheck = results.find((r) => r.name === "HTTP 500 → GeoProviderError");
    expect(errorCheck?.passed).toBe(false);
  });

  it("skips HTTP error checks for non-HTTP providers", async () => {
    const csvLike: GeoProvider = defineProvider({
      manifest: {
        id: "internal",
        name: "CSV",
        capabilities: ["search"],
        authType: "none",
        policy: { maxCacheTtlSeconds: null, canStorePermanently: true },
      },
      async searchPlaces() {
        return [
          {
            providerPlaceId: "row-1",
            name: "My Store",
            categories: ["store"],
            location: { latitude: 37.5, longitude: 127.0 },
          },
        ];
      },
    });
    const results = await runConformanceChecks(csvLike, {
      usesHttp: false,
      fixtures: { search: searchFixture },
    });
    expect(results.some((r) => r.name.includes("HTTP 500"))).toBe(false);
    expect(results.every((r) => r.passed)).toBe(true);
  });
});

describe("fixtures", () => {
  it("records and loads a fixture round-trip", async () => {
    const file = join(tmpdir(), `geowire-testkit-${process.pid}.json`);
    const data = { places: [{ id: "1", name: "Test" }] };
    await recordFixture(file, data);
    expect(await loadFixture(file)).toEqual(data);
  });
});
