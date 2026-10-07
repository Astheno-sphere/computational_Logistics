import { describe, it, expect } from "vitest";
import { ProviderRegistry } from "../src/registry.js";
import { normalizeConfig } from "../src/config/load.js";
import { createGeoWire } from "../src/geowire.js";
import { fakeProvider } from "./helpers.js";

describe("ProviderRegistry", () => {
  it("provider를 manifest.id로 등록한다", () => {
    const reg = new ProviderRegistry([fakeProvider({ id: "a" }), fakeProvider({ id: "b" })], normalizeConfig({}));
    expect(reg.has("a")).toBe(true);
    expect(reg.ids()).toEqual(new Set(["a", "b"]));
  });

  it("중복 id는 던진다", () => {
    expect(
      () => new ProviderRegistry([fakeProvider({ id: "a" }), fakeProvider({ id: "a" })], normalizeConfig({})),
    ).toThrow(/중복/);
  });

  it("config.enabled=false면 active에서 제외", () => {
    const cfg = normalizeConfig({ providers: { b: { enabled: false } } });
    const reg = new ProviderRegistry([fakeProvider({ id: "a" }), fakeProvider({ id: "b" })], cfg);
    expect(reg.active().map((r) => r.id)).toEqual(["a"]);
  });

  it("config에 없는 provider는 기본 활성 (zero-config)", () => {
    const reg = new ProviderRegistry([fakeProvider({ id: "nominatim" })], normalizeConfig({}));
    expect(reg.active().map((r) => r.id)).toEqual(["nominatim"]);
  });

  it("priority 내림차순 정렬, 동률은 id 오름차순", () => {
    const cfg = normalizeConfig({
      providers: { a: { priority: 1 }, b: { priority: 100 }, c: { priority: 1 } },
    });
    const reg = new ProviderRegistry(
      [fakeProvider({ id: "a" }), fakeProvider({ id: "b" }), fakeProvider({ id: "c" })],
      cfg,
    );
    expect(reg.active().map((r) => r.id)).toEqual(["b", "a", "c"]);
  });

  it("supporting()은 해당 capability를 선언한 provider만 반환한다", () => {
    const reg = new ProviderRegistry(
      [
        fakeProvider({ id: "search-only", capabilities: ["search"] }),
        fakeProvider({ id: "geo", capabilities: ["geocode"] }),
      ],
      normalizeConfig({}),
    );
    expect(reg.supporting("search").map((r) => r.id)).toEqual(["search-only"]);
    expect(reg.supporting("geocode").map((r) => r.id)).toEqual(["geo"]);
    expect(reg.supporting("reverseGeocode")).toEqual([]);
  });
});

describe("createGeoWire — M1 골격", () => {
  it("listProviders가 등록 provider 요약을 반환한다", () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({ id: "nominatim", name: "Nominatim", capabilities: ["search", "geocode"], search: [] }),
      ],
    });
    const list = geo.listProviders();
    expect(list).toHaveLength(1);
    expect(list[0]).toMatchObject({
      id: "nominatim",
      name: "Nominatim",
      enabled: true,
      authType: "none",
    });
  });

  it("provider 없이도 크래시 없이 생성된다 (config 경고만)", () => {
    const geo = createGeoWire({});
    expect(geo.listProviders()).toEqual([]);
  });
});
