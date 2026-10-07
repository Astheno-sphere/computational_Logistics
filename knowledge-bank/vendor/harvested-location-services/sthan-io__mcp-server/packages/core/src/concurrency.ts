import { SthanApiError } from "./client.js";

export interface ConcurrencyOptions {
  /** Max requests in flight at once. Default 10. */
  concurrency?: number;
  /** Max retry attempts for transient failures (429/503/network). Default 3. */
  retries?: number;
  /** Base delay for exponential backoff, in ms. Default 500. */
  baseDelayMs?: number;
  /** Called after each item settles (success or failure). */
  onProgress?: (completed: number, total: number) => void;
}

export interface BatchItemResult<O> {
  index: number;
  value?: O;
  error?: Error;
}

/** Transient = worth retrying. Rate limits, gateway/unavailable, and network failures. */
function isTransient(e: unknown): boolean {
  if (e instanceof SthanApiError) {
    return [429, 502, 503, 504].includes(e.statusCode);
  }
  // Timeouts and connection failures are plain Errors thrown by the client.
  return e instanceof Error;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function withRetry<O>(
  fn: () => Promise<O>,
  retries: number,
  baseDelayMs: number
): Promise<O> {
  let attempt = 0;
  for (;;) {
    try {
      return await fn();
    } catch (e) {
      if (attempt >= retries || !isTransient(e)) throw e;
      await sleep(baseDelayMs * 2 ** attempt);
      attempt++;
    }
  }
}

/**
 * Run `fn` over `items` with bounded concurrency and per-item retry/backoff.
 * Never rejects: a permanently failing item is captured as `{ error }` in its
 * slot. Results are returned in input order.
 */
export async function mapWithConcurrency<I, O>(
  items: I[],
  fn: (item: I, index: number) => Promise<O>,
  options: ConcurrencyOptions = {}
): Promise<Array<BatchItemResult<O>>> {
  const concurrency = Math.max(1, options.concurrency ?? 10);
  const retries = options.retries ?? 3;
  const baseDelayMs = options.baseDelayMs ?? 500;
  const results: Array<BatchItemResult<O>> = new Array(items.length);
  let cursor = 0;
  let completed = 0;

  async function worker(): Promise<void> {
    for (;;) {
      const index = cursor++;
      if (index >= items.length) return;
      try {
        const value = await withRetry(
          () => fn(items[index], index),
          retries,
          baseDelayMs
        );
        results[index] = { index, value };
      } catch (e) {
        results[index] = {
          index,
          error: e instanceof Error ? e : new Error(String(e)),
        };
      }
      completed++;
      options.onProgress?.(completed, items.length);
    }
  }

  const pool = Array.from(
    { length: Math.min(concurrency, items.length) },
    () => worker()
  );
  await Promise.all(pool);
  return results;
}
