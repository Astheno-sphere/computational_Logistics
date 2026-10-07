import { describe, expect, it } from "vitest";
import { defineProvider } from "../src/index.js";
import type { ProviderManifest } from "@geowirehq/schema";

const manifest: ProviderManifest = {
  id: "mock",
  name: "Mock Provider",
  capabilities: ["search"],
  authType: "none",
  policy: { maxCacheTtlSeconds: 3600, canStorePermanently: true },
};

describe("defineProvider", () => {
  it("returns the provider when manifest is valid and capabilities are implemented", () => {
    const provider = defineProvider({
      manifest,
      async searchPlaces() {
        return [];
      },
    });
    expect(provider.manifest.id).toBe("mock");
    expect(typeof provider.searchPlaces).toBe("function");
  });

  it("throws when a declared capability has no implementation", () => {
    expect(() => defineProvider({ manifest })).toThrow(/does not implement/);
  });

  it("names the missing capability and method in the error", () => {
    expect(() => defineProvider({ manifest })).toThrow(/"search" → searchPlaces/);
  });

  it("throws when the manifest is invalid", () => {
    expect(() =>
      defineProvider({
        manifest: { ...manifest, id: "Mock" }, // 대문자 id는 스키마 위반
        async searchPlaces() {
          return [];
        },
      }),
    ).toThrow(/Invalid provider manifest/);
  });
});
