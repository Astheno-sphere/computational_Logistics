import { describe, it, expect } from "vitest";
import { createTestContext, mockJson } from "@geowirehq/provider-testkit";
import { createCensusProvider } from "../src/index.js";

const GEOCODER = {
  result: {
    geographies: {
      "Census Tracts": [
        { STATE: "06", COUNTY: "075", TRACT: "020101", NAME: "Census Tract 201.01", AREALAND: 250_000 },
      ],
    },
  },
};

const ACS = [
  ["NAME", "B01003_001E", "B01002_001E", "B19013_001E", "B11001_001E", "B25010_001E", "state", "county", "tract"],
  ["Census Tract 201.01; San Francisco County; California", "4500", "38.2", "145000", "2100", "1.9", "06", "075", "020101"],
];

/** geocoder / acs URL에 따라 다른 픽스처를 돌려주는 fetch */
function routed(geocoder: unknown = GEOCODER, acs: unknown = ACS): (url: string) => Promise<Response> {
  return async (url: string) => {
    if (url.includes("/geocoder/geographies/coordinates")) return mockJson(geocoder);
    if (url.includes("/acs/acs5")) return mockJson(acs);
    return mockJson({});
  };
}

const SF = { latitude: 37.7749, longitude: -122.4194 };

describe("createCensusProvider — demographics (BYOK)", () => {
  it("키가 없으면 MISSING_CREDENTIALS를 던진다", async () => {
    const provider = createCensusProvider({});
    const ctx = createTestContext(routed());
    await expect(provider.demographics!({ location: SF }, ctx)).rejects.toMatchObject({
      code: "MISSING_CREDENTIALS",
    });
  });

  it("좌표 → tract → ACS 인구통계를 파싱한다", async () => {
    const provider = createCensusProvider({ apiKey: "test-key" });
    const p = await provider.demographics!({ location: SF }, createTestContext(routed()));
    expect(p).not.toBeNull();
    expect(p!.areaLevel).toBe("tract");
    expect(p!.areaName).toContain("San Francisco County");
    expect(p!.population).toBe(4500);
    expect(p!.medianAgeYears).toBe(38.2);
    expect(p!.medianHouseholdIncome).toEqual({ amount: 145000, currency: "USD" });
    expect(p!.households).toBe(2100);
    expect(p!.avgHouseholdSize).toBe(1.9);
    // AREALAND 250000 m² = 0.25 km² → 4500/0.25 = 18000/km²
    expect(p!.populationDensityPerSqKm).toBe(18000);
    expect(p!.source).toBe("census");
  });

  it("미국 밖(tract 없음)이면 null을 반환한다", async () => {
    const provider = createCensusProvider({ apiKey: "test-key" });
    const empty = { result: { geographies: { "Census Tracts": [] } } };
    const p = await provider.demographics!(
      { location: { latitude: 48.85, longitude: 2.35 } }, // 파리
      createTestContext(routed(empty)),
    );
    expect(p).toBeNull();
  });

  it("ACS 결측 센티넬(대형 음수)은 필드에서 생략한다", async () => {
    const provider = createCensusProvider({ apiKey: "test-key" });
    const acsMissing = [
      ["NAME", "B01003_001E", "B01002_001E", "B19013_001E", "B11001_001E", "B25010_001E", "state", "county", "tract"],
      ["Census Tract 201.01; San Francisco County; California", "4500", "-666666666", "-666666666", "2100", "1.9", "06", "075", "020101"],
    ];
    const p = await provider.demographics!({ location: SF }, createTestContext(routed(GEOCODER, acsMissing)));
    expect(p!.population).toBe(4500);
    expect(p!.medianAgeYears).toBeUndefined();
    expect(p!.medianHouseholdIncome).toBeUndefined();
  });
});
