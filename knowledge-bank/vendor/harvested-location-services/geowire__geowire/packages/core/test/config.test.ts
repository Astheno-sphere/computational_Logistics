import { describe, it, expect } from "vitest";
import { defaultConfig, GeoWireConfig } from "../src/config/schema.js";
import { substituteEnv, parseConfig, normalizeConfig } from "../src/config/load.js";
import { collectConfigWarnings } from "../src/config/warnings.js";

describe("GeoWireConfig — zero-config 기본값", () => {
  it("빈 객체를 파싱하면 모든 하위 기본값이 채워진다", () => {
    const c = defaultConfig();
    expect(c.providers).toEqual({});
    expect(c.routing.defaultStrategy).toBe("first-success");
    expect(c.routing.countries).toEqual({});
    expect(c.routing.rank).toEqual({
      distance: 40,
      openingHours: 25,
      providerConfidence: 20,
      freshness: 15,
    });
    expect(c.cache.adapter).toBe("memory");
    expect(c.cache.maxEntries).toBe(1000);
    expect(c.dedup.mergeThreshold).toBe(0.75);
    expect(c.dedup.possibleThreshold).toBe(0.6);
  });

  it("provider 항목은 enabled 기본 true", () => {
    const c = GeoWireConfig.parse({ providers: { nominatim: {}, google: { enabled: false } } });
    expect(c.providers.nominatim?.enabled).toBe(true);
    expect(c.providers.google?.enabled).toBe(false);
  });

  it("알 수 없는 provider 옵션(apiKey·source)은 통과시킨다", () => {
    const c = GeoWireConfig.parse({
      providers: { internal: { source: "./x.csv", priority: 100 } },
    });
    expect(c.providers.internal?.priority).toBe(100);
    expect((c.providers.internal as Record<string, unknown>).source).toBe("./x.csv");
  });
});

describe("substituteEnv", () => {
  it("${VAR}를 환경 변수로 치환한다", () => {
    const out = substituteEnv(
      { providers: { google: { apiKey: "${GKEY}" } } },
      { env: { GKEY: "secret123" } },
    );
    expect((out as any).providers.google.apiKey).toBe("secret123");
  });

  it("없는 변수는 기본적으로 빈 문자열", () => {
    const out = substituteEnv("${MISSING}", { env: {} });
    expect(out).toBe("");
  });

  it("strict 모드에서 없는 변수는 던진다", () => {
    expect(() => substituteEnv("${MISSING}", { env: {}, strict: true })).toThrow(/MISSING/);
  });
});

describe("parseConfig (YAML)", () => {
  it("YAML을 파싱하고 ENV 치환 후 검증한다", () => {
    const yaml = `
providers:
  nominatim: { enabled: true }
  google: { enabled: true, apiKey: \${GKEY} }
routing:
  defaultStrategy: merge
  countries:
    KR: { providers: [google, nominatim], strategy: merge }
budget:
  perRequestMaxUSD: 0.1
`;
    const c = parseConfig(yaml, { env: { GKEY: "abc" } });
    expect(c.routing.defaultStrategy).toBe("merge");
    expect(c.routing.countries.KR?.providers).toEqual(["google", "nominatim"]);
    expect((c.providers.google as any).apiKey).toBe("abc");
    expect(c.budget.perRequestMaxUSD).toBe(0.1);
  });

  it("빈 문서도 zero-config 기본값으로 파싱된다", () => {
    expect(parseConfig("").routing.defaultStrategy).toBe("first-success");
  });
});

describe("collectConfigWarnings", () => {
  it("활성 provider가 없으면 EMPTY_PROVIDERS", () => {
    const w = collectConfigWarnings(normalizeConfig({}));
    expect(w.some((x) => x.code === "EMPTY_PROVIDERS")).toBe(true);
  });

  it("평문 비밀 키를 감지한다", () => {
    const c = normalizeConfig({ providers: { google: { apiKey: "AIzaSyD-1234567890abcdef" } } });
    const w = collectConfigWarnings(c);
    expect(w.some((x) => x.code === "PLAINTEXT_SECRET" && x.provider === "google")).toBe(true);
  });

  it("${ENV} 참조는 평문으로 경고하지 않는다", () => {
    const c = normalizeConfig({ providers: { google: { apiKey: "${GKEY}" } } });
    const w = collectConfigWarnings(c);
    expect(w.some((x) => x.code === "PLAINTEXT_SECRET")).toBe(false);
  });

  it("등록되지 않은 provider id는 UNKNOWN_PROVIDER", () => {
    const c = normalizeConfig({ providers: { gooogle: { enabled: true } } });
    const w = collectConfigWarnings(c, new Set(["nominatim"]));
    expect(w.some((x) => x.code === "UNKNOWN_PROVIDER" && x.provider === "gooogle")).toBe(true);
  });
});
