import { describe, expect, it } from "vitest";
import { ProviderManifest } from "../src/index.js";

const nominatimManifest = {
  id: "nominatim",
  name: "Nominatim (OpenStreetMap)",
  capabilities: ["search", "geocode", "reverseGeocode"],
  authType: "none",
  policy: {
    maxCacheTtlSeconds: 86_400,
    canStorePermanently: true,
    attributionRequired: "© OpenStreetMap contributors",
  },
  rateLimit: { requestsPerSecond: 1 },
};

describe("ProviderManifest", () => {
  it("accepts the nominatim manifest", () => {
    const parsed = ProviderManifest.parse(nominatimManifest);
    expect(parsed.id).toBe("nominatim");
    expect(parsed.policy.attributionRequired).toContain("OpenStreetMap");
  });

  it("accepts a commercial manifest with cost and cache-forbidden policy", () => {
    const parsed = ProviderManifest.parse({
      id: "google",
      name: "Google Places",
      capabilities: ["search", "autocomplete", "geocode", "reverseGeocode", "getPlace"],
      authType: "apiKey",
      cost: {
        currency: "USD",
        perCall: { search: 0.032, geocode: 0.005 },
      },
      policy: {
        maxCacheTtlSeconds: null,
        canStorePermanently: false,
      },
    });
    expect(parsed.policy.maxCacheTtlSeconds).toBeNull();
    expect(parsed.cost?.perCall.search).toBeCloseTo(0.032);
  });

  it("rejects an empty capability list", () => {
    expect(() =>
      ProviderManifest.parse({ ...nominatimManifest, capabilities: [] }),
    ).toThrow();
  });

  it("rejects an uppercase provider id", () => {
    expect(() =>
      ProviderManifest.parse({ ...nominatimManifest, id: "Nominatim" }),
    ).toThrow();
  });

  it("rejects unknown capabilities in cost.perCall", () => {
    expect(() =>
      ProviderManifest.parse({
        ...nominatimManifest,
        cost: { currency: "USD", perCall: { teleport: 1 } },
      }),
    ).toThrow();
  });
});
