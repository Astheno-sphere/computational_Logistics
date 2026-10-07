import { describe, it, expect } from "vitest";
import { createGeoWire } from "../src/geowire.js";
import { fakeProvider, place } from "./helpers.js";

describe("getPlace", () => {
  it("provider:providerPlaceId 참조로 상세를 조회한다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "google",
          capabilities: ["search", "getPlace"],
          policy: { maxCacheTtlSeconds: null, canStorePermanently: false },
          search: [place({ providerPlaceId: "ChIJ1", name: "GS25 강남점", location: { latitude: 37.5, longitude: 127 } })],
        }),
      ],
    });
    const p = await geo.getPlace({ id: "google:ChIJ1" });
    expect(p).not.toBeNull();
    expect(p!.name).toBe("GS25 강남점");
    expect(p!.sources[0]!.provider).toBe("google");
    expect(p!.id).toMatch(/^gwp_/);
  });

  it("내부 gwp_ ID는 역추적 불가라 null (v0.1)", async () => {
    const geo = createGeoWire({ providers: [fakeProvider({ id: "google", capabilities: ["getPlace"], search: [] })] });
    expect(await geo.getPlace({ id: "gwp_abcdef" })).toBeNull();
  });

  it("등록되지 않은 공급자 참조는 null", async () => {
    const geo = createGeoWire({ providers: [fakeProvider({ id: "google", capabilities: ["getPlace"], search: [] })] });
    expect(await geo.getPlace({ id: "unknown:x" })).toBeNull();
  });

  it("getPlace 미지원 공급자는 null", async () => {
    const geo = createGeoWire({ providers: [fakeProvider({ id: "nominatim", capabilities: ["search"], search: [] })] });
    expect(await geo.getPlace({ id: "nominatim:node/1" })).toBeNull();
  });

  it("공급자 실패는 GeoProviderError로 전파한다", async () => {
    const geo = createGeoWire({
      providers: [fakeProvider({ id: "google", capabilities: ["getPlace"], failWith: "PROVIDER_UNAVAILABLE" })],
    });
    await expect(geo.getPlace({ id: "google:x" })).rejects.toMatchObject({ code: "PROVIDER_UNAVAILABLE" });
  });
});
