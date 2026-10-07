import { describe, expect, it } from "vitest";
import { CountryCode } from "../src/index.js";

describe("CountryCode", () => {
  it("normalizes case and surrounding whitespace", () => {
    expect(CountryCode.parse("vn")).toBe("VN");
    expect(CountryCode.parse("  kr ")).toBe("KR");
  });

  it("accepts assigned ISO 3166-1 alpha-2 codes", () => {
    expect(CountryCode.parse("US")).toBe("US");
  });

  it("rejects two-letter values that are not assigned codes", () => {
    expect(() => CountryCode.parse("ZZ")).toThrow();
    expect(() => CountryCode.parse("XX")).toThrow();
  });

  it("rejects non-alpha and wrong-length values", () => {
    expect(() => CountryCode.parse("12")).toThrow();
    expect(() => CountryCode.parse("??")).toThrow();
    expect(() => CountryCode.parse("KOR")).toThrow();
  });
});
