import { describe, expect, it } from "vitest";
import { RateLimiter } from "../src/rate-limit.js";

describe("RateLimiter", () => {
  it("spaces successive calls by the interval when time does not advance", async () => {
    const slept: number[] = [];
    const limiter = new RateLimiter(1000, async (ms) => {
      slept.push(ms);
    });
    await limiter.acquire(0);
    await limiter.acquire(0);
    await limiter.acquire(0);
    expect(slept).toEqual([1000, 2000]);
  });

  it("does not wait when enough time has already elapsed", async () => {
    const slept: number[] = [];
    const limiter = new RateLimiter(1000, async (ms) => {
      slept.push(ms);
    });
    await limiter.acquire(0);
    await limiter.acquire(1000);
    await limiter.acquire(2000);
    expect(slept).toEqual([]);
  });
});
