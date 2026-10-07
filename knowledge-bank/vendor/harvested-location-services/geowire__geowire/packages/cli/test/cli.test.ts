import { describe, it, expect } from "vitest";
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createGeoWire, type GeoWire } from "@geowirehq/core";
import { createNominatimProvider } from "@geowirehq/provider-nominatim";
import type { IO } from "../src/io.js";
import { parseFlags, parseNear, flagInt } from "../src/args.js";
import { parseDotEnv, buildEnvContent, ensureGitignore } from "../src/env.js";
import { buildEnvVars, buildConfigYaml, runInit } from "../src/commands/init.js";
import { runSearch } from "../src/commands/search.js";
import { runReverse } from "../src/commands/reverse.js";
import { runGet } from "../src/commands/get.js";
import { runTest } from "../src/commands/test.js";
import { formatPlace } from "../src/format.js";
import { run } from "../src/cli.js";
import type { Place } from "@geowirehq/schema";

const NOMI = [
  {
    osm_type: "node",
    osm_id: 1,
    lat: "37.4979",
    lon: "127.0276",
    name: "블루보틀 강남",
    display_name: "블루보틀 강남, 테헤란로, 강남구, 서울",
    category: "amenity",
    type: "cafe",
    importance: 0.4,
    address: { road: "테헤란로", city: "서울", country_code: "kr" },
  },
];

function fixtureGeo(): GeoWire {
  return createGeoWire({
    providers: [createNominatimProvider({ sleep: async () => {} })],
    baseFetch: async () => new Response(JSON.stringify(NOMI), { headers: { "content-type": "application/json" } }),
  });
}

function capture(): { io: IO; out: string[]; err: string[] } {
  const out: string[] = [];
  const err: string[] = [];
  return { io: { out: (l) => out.push(l), err: (l) => err.push(l) }, out, err };
}

describe("args 파서", () => {
  it("위치 인자와 플래그를 분리한다", () => {
    const { _, flags } = parseFlags(["coffee", "near", "me", "--limit", "5", "--json"]);
    expect(_).toEqual(["coffee", "near", "me"]);
    expect(flags).toEqual({ limit: "5", json: true });
  });

  it("parseNear는 'lat,lon'을 파싱한다", () => {
    expect(parseNear("37.5,127.0")).toEqual({ latitude: 37.5, longitude: 127 });
    expect(parseNear("bad")).toBeUndefined();
  });

  it("flagInt", () => {
    expect(flagInt("10")).toBe(10);
    expect(flagInt(true)).toBeUndefined();
  });
});

describe("env 유틸", () => {
  it("parseDotEnv는 주석·따옴표를 처리한다", () => {
    expect(parseDotEnv('# c\nA=1\nB="two words"\n')).toEqual({ A: "1", B: "two words" });
  });

  it("buildEnvContent는 헤더 + KEY=value", () => {
    const c = buildEnvContent({ GOOGLE_MAPS_API_KEY: "abc" });
    expect(c).toContain("GOOGLE_MAPS_API_KEY=abc");
    expect(c).toContain("# GeoWire");
  });

  it("ensureGitignore는 없으면 추가, 있으면 no-op", () => {
    const dir = mkdtempSync(join(tmpdir(), "gw-"));
    const gi = join(dir, ".gitignore");
    expect(ensureGitignore(gi, ".env")).toBe(true);
    expect(readFileSync(gi, "utf8")).toContain(".env");
    expect(ensureGitignore(gi, ".env")).toBe(false); // 이미 있음
  });
});

describe("init 순수 로직", () => {
  it("buildEnvVars", () => {
    expect(buildEnvVars({ strategy: "merge", google: { apiKey: "K" }, internal: { csvPath: "./p.csv" } })).toEqual({
      GOOGLE_MAPS_API_KEY: "K",
      GEOWIRE_INTERNAL_CSV: "./p.csv",
    });
  });

  it("buildConfigYaml은 ${ENV} 참조를 쓰고 평문 키를 넣지 않는다", () => {
    const yaml = buildConfigYaml({ strategy: "merge", google: { apiKey: "SECRET" } });
    expect(yaml).toContain("apiKey: ${GOOGLE_MAPS_API_KEY}");
    expect(yaml).not.toContain("SECRET");
    expect(yaml).toContain("defaultStrategy: merge");
  });
});

describe("runInit 마법사 (파일 생성)", () => {
  it("답변에 따라 .env·config·.gitignore를 생성한다", async () => {
    const dir = mkdtempSync(join(tmpdir(), "gw-init-"));
    const answers = ["y", "AIzaSyTESTKEY123", "n", "y"]; // google? key, internal? no, merge? yes
    let i = 0;
    const { io, out } = capture();
    const code = await runInit({ ask: async () => answers[i++]!, cwd: dir, io });

    expect(code).toBe(0);
    expect(existsSync(join(dir, ".env"))).toBe(true);
    expect(readFileSync(join(dir, ".env"), "utf8")).toContain("GOOGLE_MAPS_API_KEY=AIzaSyTESTKEY123");
    expect(readFileSync(join(dir, "geowire.config.yaml"), "utf8")).toContain("defaultStrategy: merge");
    expect(readFileSync(join(dir, ".gitignore"), "utf8")).toContain(".env");
    expect(out.join("\n")).toContain("geowire search");
  });

  it("provider 미선택 시 .env 없이 config만 생성", async () => {
    const dir = mkdtempSync(join(tmpdir(), "gw-init2-"));
    const answers = ["n", "n"]; // google no, internal no (merge 안 물음)
    let i = 0;
    const { io } = capture();
    await runInit({ ask: async () => answers[i++]!, cwd: dir, io });
    expect(existsSync(join(dir, ".env"))).toBe(false);
    expect(existsSync(join(dir, "geowire.config.yaml"))).toBe(true);
  });
});

describe("runSearch", () => {
  it("테이블 출력에 이름·출처·응답시간을 담는다", async () => {
    const { io, out } = capture();
    const code = await runSearch(fixtureGeo(), { query: "coffee" }, io);
    expect(code).toBe(0);
    const text = out.join("\n");
    expect(text).toContain("블루보틀 강남");
    expect(text).toContain("nominatim");
    expect(text).toContain("Found 1 place");
  });

  it("--json은 원시 응답을 출력한다", async () => {
    const { io, out } = capture();
    await runSearch(fixtureGeo(), { query: "coffee", json: true }, io);
    const parsed = JSON.parse(out.join("\n"));
    expect(parsed.results[0].name).toBe("블루보틀 강남");
    expect(parsed.meta.strategy).toBeDefined();
  });

  it("near를 주면 거리 열이 채워진다", async () => {
    const { io, out } = capture();
    await runSearch(fixtureGeo(), { query: "coffee", near: { latitude: 37.498, longitude: 127.028 } }, io);
    expect(out.join("\n")).toMatch(/\d+m/);
  });
});

describe("runReverse", () => {
  it("좌표를 표로 리버스 지오코딩한다", async () => {
    const { io, out } = capture();
    const code = await runReverse(fixtureGeo(), { location: { latitude: 37.4979, longitude: 127.0276 } }, io);
    expect(code).toBe(0);
    expect(out.join("\n")).toContain("블루보틀 강남");
  });

  it("--json은 원시 응답을 출력한다", async () => {
    const { io, out } = capture();
    await runReverse(fixtureGeo(), { location: { latitude: 37.4979, longitude: 127.0276 }, json: true }, io);
    expect(JSON.parse(out.join("\n")).results[0].name).toBe("블루보틀 강남");
  });
});

describe("runGet", () => {
  it("getPlace 미지원 참조는 에러(1)를 반환한다", async () => {
    const { io, err } = capture();
    const code = await runGet(fixtureGeo(), { id: "nominatim:node/1" }, io);
    expect(code).toBe(1);
    expect(err.join("\n")).toContain("No place found");
  });
});

describe("formatPlace", () => {
  it("이름·주소·좌표·연락처·출처를 렌더한다", () => {
    const p: Place = {
      id: "gwp_google_x",
      name: "Blue Bottle",
      categories: ["cafe"],
      location: { latitude: 37.5, longitude: 127.0 },
      address: { formatted: "1 Teheran-ro, Seoul" },
      contact: { phone: "+82-2-000-0000", website: "https://example.com" },
      business: { openingHours: "Mon-Fri 08:00-20:00", rating: 4.5, priceLevel: 2 },
      sources: [{ provider: "google", providerPlaceId: "x", fetchedAt: "2026-07-18T00:00:00.000Z" }],
      attributions: ["© Google"],
    };
    const text = formatPlace(p);
    expect(text).toContain("Blue Bottle");
    expect(text).toContain("1 Teheran-ro, Seoul");
    expect(text).toContain("(37.5, 127)");
    expect(text).toContain("hours: Mon-Fri 08:00-20:00");
    expect(text).toContain("phone: +82-2-000-0000");
    expect(text).toContain("google:x");
    expect(text).toContain("© Google");
  });
});

describe("runTest", () => {
  it("연결된 공급자를 ✓로 보고한다", async () => {
    const { io, out } = capture();
    const code = await runTest(fixtureGeo(), io);
    expect(code).toBe(0);
    expect(out.join("\n")).toContain("✓ Nominatim (OpenStreetMap) connected");
  });
});

describe("run 라우팅", () => {
  it("help는 사용법을 출력한다", async () => {
    const { io, out } = capture();
    expect(await run(["help"], io)).toBe(0);
    expect(out.join("\n")).toContain("Usage:");
  });

  it("version", async () => {
    const { io, out } = capture();
    await run(["version"], io);
    expect(out.join("\n")).toContain("geowire 0.1.2");
  });

  it("search without query → 사용법 에러(1)", async () => {
    const { io, err } = capture();
    expect(await run(["search"], io)).toBe(1);
    expect(err.join("\n")).toContain("usage: geowire search");
  });

  it("reverse without coords → 사용법 에러(1)", async () => {
    const { io, err } = capture();
    expect(await run(["reverse"], io)).toBe(1);
    expect(err.join("\n")).toContain("usage: geowire reverse");
  });

  it("get without id → 사용법 에러(1)", async () => {
    const { io, err } = capture();
    expect(await run(["get"], io)).toBe(1);
    expect(err.join("\n")).toContain("usage: geowire get");
  });

  it("알 수 없는 명령 → 1", async () => {
    const { io } = capture();
    expect(await run(["frobnicate"], io)).toBe(1);
  });
});
