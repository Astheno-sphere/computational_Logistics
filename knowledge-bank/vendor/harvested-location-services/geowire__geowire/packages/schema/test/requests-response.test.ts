import { describe, expect, it } from "vitest";
import {
  SearchPlacesRequest,
  ResponseMeta,
  generateJsonSchemas,
} from "../src/index.js";

describe("SearchPlacesRequest", () => {
  it("applies the default limit", () => {
    const parsed = SearchPlacesRequest.parse({ query: "24-hour pharmacy" });
    expect(parsed.limit).toBe(10);
  });

  it("accepts near + options overrides and normalizes country", () => {
    const parsed = SearchPlacesRequest.parse({
      query: "pharmacy",
      near: { latitude: 10.78, longitude: 106.69 },
      country: "vn",
      openNow: true,
      options: { strategy: "merge", maxCostUSD: 0.05 },
    });
    expect(parsed.options?.strategy).toBe("merge");
    expect(parsed.country).toBe("VN");
  });

  it("rejects an unknown strategy", () => {
    expect(() =>
      SearchPlacesRequest.parse({
        query: "pharmacy",
        options: { strategy: "yolo" },
      }),
    ).toThrow();
  });

  it("accepts cost-aware / weighted / fastest strategies", () => {
    for (const strategy of ["cost-aware", "weighted", "fastest"]) {
      const parsed = SearchPlacesRequest.parse({ query: "pharmacy", options: { strategy } });
      expect(parsed.options?.strategy).toBe(strategy);
    }
  });
});

describe("ResponseMeta", () => {
  it("defaults skipped/failed/attributions to empty arrays", () => {
    const parsed = ResponseMeta.parse({
      providersUsed: [{ provider: "nominatim", resultCount: 18, latencyMs: 240 }],
      strategy: "first-success",
    });
    expect(parsed.providersSkipped).toEqual([]);
    expect(parsed.attributions).toEqual([]);
  });

  it("records skipped providers with a normalized reason", () => {
    const parsed = ResponseMeta.parse({
      providersUsed: [],
      providersSkipped: [{ provider: "google", reason: "MISSING_CREDENTIALS" }],
      strategy: "merge",
    });
    expect(parsed.providersSkipped[0]?.reason).toBe("MISSING_CREDENTIALS");
  });
});

describe("generateJsonSchemas", () => {
  it("generates JSON Schema for every public spec", () => {
    const schemas = generateJsonSchemas();
    expect(Object.keys(schemas)).toContain("place/v1");
    expect(Object.keys(schemas)).toContain("provider-manifest/v1");
    const place = schemas["place/v1"] as { type?: string; required?: string[] };
    expect(place.type).toBe("object");
    expect(place.required).toContain("sources");
  });
});
