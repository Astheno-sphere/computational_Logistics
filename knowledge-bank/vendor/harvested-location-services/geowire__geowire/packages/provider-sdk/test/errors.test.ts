import { describe, expect, it } from "vitest";
import { errorFromHttpStatus, isRetryableCode, GeoProviderError } from "../src/index.js";

describe("errorFromHttpStatus", () => {
  it.each([
    [401, "AUTH_FAILED", false],
    [403, "AUTH_FAILED", false],
    [429, "RATE_LIMITED", true],
    [400, "INVALID_REQUEST", false],
    [422, "INVALID_REQUEST", false],
    [408, "TIMEOUT", true],
    [504, "TIMEOUT", true],
    [500, "PROVIDER_UNAVAILABLE", true],
    [503, "PROVIDER_UNAVAILABLE", true],
    [501, "UNSUPPORTED_CAPABILITY", false],
  ] as const)("maps HTTP %i to %s (retryable=%s)", (status, code, retryable) => {
    const err = errorFromHttpStatus(status, { provider: "google" });
    expect(err).toBeInstanceOf(GeoProviderError);
    expect(err.code).toBe(code);
    expect(err.status).toBe(status);
    expect(err.provider).toBe("google");
    expect(err.retryable).toBe(retryable);
  });

  it("exposes retryability via isRetryableCode", () => {
    expect(isRetryableCode("TIMEOUT")).toBe(true);
    expect(isRetryableCode("RATE_LIMITED")).toBe(true);
    expect(isRetryableCode("AUTH_FAILED")).toBe(false);
  });
});
