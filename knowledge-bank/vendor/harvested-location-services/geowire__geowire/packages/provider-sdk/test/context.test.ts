import { describe, expect, it } from "vitest";
import { createRetryingFetch, noopLogger, GeoProviderError } from "../src/index.js";

function res(status: number, body: unknown = {}, headers: HeadersInit = {}): Response {
  return new Response(JSON.stringify(body), { status, headers });
}

const deps = { logger: noopLogger, now: () => 0 };

describe("createRetryingFetch", () => {
  it("retries on 503 then returns the success response", async () => {
    const queue = [res(503), res(200, { ok: true })];
    let calls = 0;
    const f = createRetryingFetch(
      { ...deps, baseFetch: async () => queue[calls++]! },
      { backoffBaseMs: 1 },
    );
    const out = await f("http://x");
    expect(out.status).toBe(200);
    expect(calls).toBe(2);
  });

  it("does not retry 4xx and returns it as-is", async () => {
    let calls = 0;
    const f = createRetryingFetch(
      {
        ...deps,
        baseFetch: async () => {
          calls++;
          return res(404);
        },
      },
      { backoffBaseMs: 1 },
    );
    const out = await f("http://x");
    expect(out.status).toBe(404);
    expect(calls).toBe(1);
  });

  it("returns the last retryable response after exhausting retries", async () => {
    let calls = 0;
    const f = createRetryingFetch(
      {
        ...deps,
        baseFetch: async () => {
          calls++;
          return res(503);
        },
      },
      { retries: 2, backoffBaseMs: 1 },
    );
    const out = await f("http://x");
    expect(out.status).toBe(503);
    expect(calls).toBe(3); // 1 initial + 2 retries
  });

  it("throws normalized TIMEOUT after exhausting retries on network error", async () => {
    const f = createRetryingFetch(
      {
        ...deps,
        baseFetch: async () => {
          throw new Error("ECONNREFUSED");
        },
      },
      { retries: 1, backoffBaseMs: 1 },
    );
    const err = await f("http://x").catch((e) => e);
    expect(err).toBeInstanceOf(GeoProviderError);
    expect(err.code).toBe("TIMEOUT");
  });

  it("aborts immediately when the caller signal is already aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    const f = createRetryingFetch(
      { ...deps, baseFetch: async () => res(200), signal: controller.signal },
      { backoffBaseMs: 1 },
    );
    const err = await f("http://x").catch((e) => e);
    expect(err).toBeInstanceOf(GeoProviderError);
    expect(err.code).toBe("TIMEOUT");
  });

  it("honors Retry-After header for the backoff delay", async () => {
    const queue = [res(429, {}, { "retry-after": "0" }), res(200)];
    let calls = 0;
    const f = createRetryingFetch(
      { ...deps, baseFetch: async () => queue[calls++]! },
      { backoffBaseMs: 1 },
    );
    const out = await f("http://x");
    expect(out.status).toBe(200);
    expect(calls).toBe(2);
  });
});
