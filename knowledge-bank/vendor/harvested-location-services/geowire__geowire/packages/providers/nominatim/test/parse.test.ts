import { describe, expect, it } from "vitest";
import { ProviderPlace } from "@geowirehq/provider-sdk";
import { parseResult, parseResults, mapCategory } from "../src/index.js";

const hcmPharmacy = {
  osm_type: "node",
  osm_id: 123,
  place_id: 1,
  lat: "10.7769",
  lon: "106.7009",
  name: "Pharmacity",
  display_name: "Pharmacity, Nguyễn Huệ, Bến Nghé, Quận 1, Hồ Chí Minh, Việt Nam",
  category: "amenity",
  type: "pharmacy",
  importance: 0.35,
  addresstype: "amenity",
  address: {
    road: "Nguyễn Huệ",
    suburb: "Bến Nghé",
    city: "Hồ Chí Minh",
    country: "Việt Nam",
    country_code: "vn",
    postcode: "70000",
  },
};

describe("parseResult", () => {
  it("maps a search result to a schema-valid ProviderPlace", () => {
    const place = parseResult(hcmPharmacy);
    expect(place).not.toBeNull();
    expect(ProviderPlace.safeParse(place).success).toBe(true);
    expect(place?.providerPlaceId).toBe("node/123");
    expect(place?.categories).toEqual(["pharmacy"]);
    expect(place?.location).toEqual({ latitude: 10.7769, longitude: 106.7009 });
    expect(place?.address?.country).toBe("VN"); // 소문자 vn → 정규화·검증
    expect(place?.address?.street).toBe("Nguyễn Huệ");
    expect(place?.confidence).toBeCloseTo(0.35);
  });

  it("returns null when coordinates are missing or invalid", () => {
    expect(parseResult({ osm_type: "node", osm_id: 1 })).toBeNull();
    expect(parseResult({ osm_type: "node", osm_id: 1, lat: "abc", lon: "1" })).toBeNull();
  });

  it("derives a name from display_name when name is empty", () => {
    const place = parseResult({
      osm_type: "way",
      osm_id: 9,
      lat: "37.5665",
      lon: "126.978",
      name: "",
      display_name: "Seoul, South Korea",
      category: "boundary",
      type: "administrative",
      address: { country_code: "kr" },
    });
    expect(place?.name).toBe("Seoul");
    expect(place?.address?.country).toBe("KR");
    expect(place?.categories).toEqual(["administrative"]); // 미매핑 → 원본 type
  });

  it("drops an out-of-range country_code instead of failing validation", () => {
    const place = parseResult({
      ...hcmPharmacy,
      address: { ...hcmPharmacy.address, country_code: "zz" },
    });
    expect(ProviderPlace.safeParse(place).success).toBe(true);
    expect(place?.address?.country).toBeUndefined();
  });
});

describe("parseResults", () => {
  it("accepts both a single object (reverse) and an array (search)", () => {
    expect(parseResults(hcmPharmacy)).toHaveLength(1);
    expect(parseResults([hcmPharmacy, hcmPharmacy])).toHaveLength(2);
    expect(parseResults(null)).toHaveLength(0);
  });
});

describe("mapCategory", () => {
  it("maps known OSM tags and falls back to the raw type", () => {
    expect(mapCategory("amenity", "pharmacy")).toEqual(["pharmacy"]);
    expect(mapCategory("shop", "convenience")).toEqual(["convenience"]);
    expect(mapCategory("boundary", "administrative")).toEqual(["administrative"]);
    expect(mapCategory(undefined, undefined)).toEqual([]);
  });
});
