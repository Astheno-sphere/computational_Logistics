import { describe, it, expect } from "vitest";
import { makePlaceId, parsePlaceRef } from "../src/ids.js";

describe("makePlaceId", () => {
  it("gwp_ 접두 + Place.id 정규식을 만족한다", () => {
    const id = makePlaceId("nominatim", "node/123");
    expect(id).toMatch(/^gwp_[A-Za-z0-9_-]+$/);
  });

  it("같은 입력은 항상 같은 ID (안정적)", () => {
    expect(makePlaceId("google", "ChIJabc")).toBe(makePlaceId("google", "ChIJabc"));
  });

  it("provider나 placeId가 다르면 ID가 다르다", () => {
    expect(makePlaceId("google", "x")).not.toBe(makePlaceId("nominatim", "x"));
    expect(makePlaceId("google", "x")).not.toBe(makePlaceId("google", "y"));
  });
});

describe("parsePlaceRef", () => {
  it("gwp_ ID는 internal로 분류", () => {
    expect(parsePlaceRef("gwp_abc")).toEqual({ kind: "internal", id: "gwp_abc" });
  });

  it("provider:id는 ref로 분해", () => {
    expect(parsePlaceRef("google:ChIJ:abc")).toEqual({
      kind: "ref",
      ref: { provider: "google", providerPlaceId: "ChIJ:abc" },
    });
  });

  it("접두사·콜론 없으면 internal로 관대하게 해석", () => {
    expect(parsePlaceRef("plainid")).toEqual({ kind: "internal", id: "plainid" });
  });
});
