const REQUEST_TIMEOUT_MS = 30_000;
const MAX_CACHE_ENTRIES = 500;
/** Hard cap on a buffered upstream response — protects the process heap. */
const MAX_RESPONSE_BYTES = 8 * 1024 * 1024;
/** Responses above this are served but never cached. */
const MAX_CACHEABLE_CHARS = 1024 * 1024;
/**
 * Aggregate budget for cached response text. The entry cap alone would allow
 * 500 × 1 MB — half a gigabyte held for a full hour in a memory-limited
 * container.
 */
const MAX_CACHE_BYTES = 32 * 1024 * 1024;
/** Beyond this many queued requests per service the caller gets a fast error. */
const MAX_QUEUE_DEPTH = 32;

export class OsmApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: string,
    public readonly service: string,
    url: string
  ) {
    super(`${service} request to ${redactUrl(url)} failed with HTTP ${status}`);
    this.name = 'OsmApiError';
  }
}

/**
 * Query strings can carry credentials (an operator-supplied base URL might
 * embed one) — never let any of the common key parameter names into an error
 * message.
 */
export function redactUrl(url: string): string {
  return url.replace(
    /([?&](?:api_?key|key|token|access_token)=)[^&]*/gi,
    '$1[redacted]'
  );
}

/**
 * Serializes requests to one upstream service and enforces a minimum interval
 * between them. This is what keeps the server inside the published usage
 * policies (Nominatim and the FOSSGIS OSRM instance both allow at most one
 * request per second per client). The queue depth is capped: beyond it the
 * caller gets an immediate "busy" error instead of a multi-minute silent wait
 * that would outlive the MCP client's patience anyway.
 */
export class RateLimiter {
  private nextSlot = 0;
  private queue: Promise<void> = Promise.resolve();
  private pending = 0;

  constructor(
    private readonly intervalMs: number,
    private readonly now: () => number = () => Date.now(),
    private readonly sleep: (ms: number) => Promise<void> = (ms) =>
      new Promise((resolve) => setTimeout(resolve, ms)),
    private readonly maxQueue: number = MAX_QUEUE_DEPTH
  ) {}

  acquire(): Promise<void> {
    if (this.pending >= this.maxQueue) {
      return Promise.reject(
        new Error(
          'too many queued requests for this service — the rate-limit queue ' +
            'is full; retry in a moment or batch fewer locations per call'
        )
      );
    }
    this.pending += 1;
    const turn = this.queue
      .then(async () => {
        const wait = this.nextSlot - this.now();
        this.nextSlot = Math.max(this.now(), this.nextSlot) + this.intervalMs;
        if (wait > 0) {
          await this.sleep(wait);
        }
      })
      .finally(() => {
        this.pending -= 1;
      });
    // Swallow rejections on the internal chain; callers see them via `turn`.
    this.queue = turn.catch(() => {});
    return turn;
  }
}

/** Caps how many requests run against one service at the same time. */
export class Semaphore {
  private active = 0;
  private readonly waiters: Array<() => void> = [];

  constructor(private readonly max: number) {}

  async acquire(): Promise<() => void> {
    if (this.active >= this.max) {
      // The releaser hands its slot over without decrementing `active`, so a
      // concurrent fresh acquire() in the same microtask window still sees the
      // semaphore as full — decrement-then-resolve would briefly over-admit.
      await new Promise<void>((resolve) => this.waiters.push(resolve));
    } else {
      this.active += 1;
    }
    let released = false;
    return () => {
      if (released) return;
      released = true;
      const next = this.waiters.shift();
      if (next) {
        next();
      } else {
        this.active -= 1;
      }
    };
  }
}

interface CacheEntry {
  expires: number;
  value: unknown;
  /** Length of the response text this entry was parsed from. */
  size: number;
}

/**
 * In-memory TTL cache with a hard entry cap and an aggregate size budget
 * (oldest entries are evicted first).
 */
export class TtlCache {
  private readonly entries = new Map<string, CacheEntry>();
  private totalSize = 0;

  constructor(
    private readonly ttlMs: number,
    private readonly maxEntries: number = MAX_CACHE_ENTRIES,
    private readonly now: () => number = () => Date.now(),
    private readonly maxBytes: number = MAX_CACHE_BYTES
  ) {}

  get(key: string): unknown {
    const entry = this.entries.get(key);
    if (!entry) return undefined;
    if (entry.expires <= this.now()) {
      this.delete(key);
      return undefined;
    }
    return entry.value;
  }

  set(key: string, value: unknown, size = 0): void {
    if (this.ttlMs <= 0 || size > this.maxBytes) return;
    this.delete(key);
    while (
      this.entries.size > 0 &&
      (this.entries.size >= this.maxEntries ||
        this.totalSize + size > this.maxBytes)
    ) {
      const oldest = this.entries.keys().next().value;
      if (oldest === undefined) break;
      this.delete(oldest);
    }
    this.entries.set(key, { expires: this.now() + this.ttlMs, value, size });
    this.totalSize += size;
  }

  private delete(key: string): void {
    const entry = this.entries.get(key);
    if (!entry) return;
    this.totalSize -= entry.size;
    this.entries.delete(key);
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST';
  headers?: Record<string, string>;
  body?: string;
  /** Skip the response cache, e.g. for endpoints with volatile output. */
  noCache?: boolean;
  timeoutMs?: number;
}

/**
 * Fetch wrapper shared by all backends: sends the identifying User-Agent,
 * never follows redirects, times out, caps the buffered response size, caches
 * identical requests for the configured TTL and throttles per service via the
 * caller-supplied limiter.
 */
export class HttpClient {
  private readonly cache: TtlCache;

  constructor(
    private readonly userAgent: string,
    cacheTtlMs: number,
    cache?: TtlCache
  ) {
    this.cache = cache ?? new TtlCache(cacheTtlMs);
  }

  async request(
    service: string,
    url: string,
    limiter: RateLimiter | null,
    options: RequestOptions = {}
  ): Promise<unknown> {
    const method = options.method ?? 'GET';
    const cacheKey = `${service} ${method} ${url} ${options.body ?? ''}`;
    if (!options.noCache) {
      const cached = this.cache.get(cacheKey);
      if (cached !== undefined) return cached;
    }

    if (limiter) await limiter.acquire();

    const response = await fetch(url, {
      method,
      headers: {
        'User-Agent': this.userAgent,
        Accept: 'application/json',
        ...options.headers,
      },
      body: options.body ?? null,
      // Never follow a redirect: headers would be resent to whatever host the
      // upstream points at.
      redirect: 'error',
      signal: AbortSignal.timeout(options.timeoutMs ?? REQUEST_TIMEOUT_MS),
    });
    // Status first. The body of an error answer is read under its own, much
    // smaller ceiling that cuts instead of refusing: a 5xx with a body past
    // the data cap used to surface as a size error — a plain Error with no
    // status — so the Overpass mirror failover and the 429 hint, both keyed
    // on the status, never saw it.
    if (!response.ok) {
      const body = await readErrorBody(response);
      throw new OsmApiError(response.status, body, service, url);
    }
    const text = await readBodyCapped(response, service);

    let data: unknown = text;
    const contentType = response.headers.get('content-type') ?? '';
    if (contentType.includes('json') || looksLikeJson(text)) {
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
    }
    if (!options.noCache && text.length <= MAX_CACHEABLE_CHARS) {
      this.cache.set(cacheKey, data, text.length);
    }
    return data;
  }
}

/**
 * Buffers the response body up to MAX_RESPONSE_BYTES and aborts beyond it —
 * an overloaded (or hostile) upstream must not be able to exhaust the heap.
 */
async function readBodyCapped(
  response: Response,
  service: string
): Promise<string> {
  const declared = Number(response.headers.get('content-length') ?? '0');
  if (declared > MAX_RESPONSE_BYTES) {
    throw new Error(
      `${service} response is too large (${declared} bytes, cap ${MAX_RESPONSE_BYTES})`
    );
  }
  if (!response.body) {
    return response.text();
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let received = 0;
  let text = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    received += value.byteLength;
    if (received > MAX_RESPONSE_BYTES) {
      await reader.cancel();
      throw new Error(
        `${service} response exceeded the ${MAX_RESPONSE_BYTES}-byte cap`
      );
    }
    text += decoder.decode(value, { stream: true });
  }
  return text + decoder.decode();
}

/** Ceiling on what is read of an error body; the rest is cut, never refused. */
const MAX_ERROR_BODY_BYTES = 64 * 1024;

/**
 * Reads the body of a non-2xx answer up to MAX_ERROR_BODY_BYTES and drops the
 * rest. Nothing downstream needs more — `sanitizeErrorBody` shows at most
 * 2000 characters of it — and an error body is the one an upstream gets to
 * choose freely, so its size must not decide what kind of error this is.
 */
async function readErrorBody(response: Response): Promise<string> {
  if (!response.body) {
    return response.text();
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let received = 0;
  let text = '';
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      received += value.byteLength;
      if (received > MAX_ERROR_BODY_BYTES) {
        const keep = value.byteLength - (received - MAX_ERROR_BODY_BYTES);
        text += decoder.decode(value.subarray(0, keep), { stream: true });
        await reader.cancel();
        return text + decoder.decode();
      }
      text += decoder.decode(value, { stream: true });
    }
  } catch {
    // A body that fails half-way is still an error answer with that status;
    // what was read so far is all the detail there is.
  }
  return text + decoder.decode();
}

function looksLikeJson(text: string): boolean {
  const trimmed = text.trimStart();
  return trimmed.startsWith('{') || trimmed.startsWith('[');
}

const MAX_ERROR_BODY_LENGTH = 2000;

/*
 * C0 and C1 controls, DEL, and the BiDi overrides and isolates.
 *
 * The error path is the one place in this server where third-party text reaches
 * the model with no JSON encoding in between — the body is concatenated straight
 * into the text block — so an ANSI escape here is an ANSI escape in whatever
 * renders the result. That matters more than it sounds: the default
 * `OVERPASS_BASE_URL` is a community mirror this project does not run, and an
 * error body is exactly what a mirror gets to choose.
 *
 * Stricter than the class the data path uses, which keeps U+200E and U+200F
 * because OSM place names need them. An error body has no place name to protect.
 * Tab, newline and carriage return stay: they are the body's own formatting.
 */
const UNSAFE_CHARS =
  // eslint-disable-next-line no-control-regex
  /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u200e\u200f\u202a-\u202e\u2066-\u2069]/g;

/**
 * Limits what an upstream error body can inject into the model context: HTML
 * error pages are dropped entirely, control characters are stripped and other
 * bodies are truncated. Bodies often echo the request line, so URL-style key
 * parameters are redacted here too.
 *
 * The strip is repeated in `errorResult`, which is the funnel every error text
 * passes through. Both, deliberately: this function promises a body that is safe
 * to concatenate, and a promise that only holds because of what the caller does
 * afterwards is not one.
 */
/**
 * A fragment of text the upstream wrote, made safe for an error message: a
 * string only (anything else is described, not printed), control characters
 * stripped, cut to `max` characters and labelled as what it is. OSRM's
 * `code`/`message` fields used to go into the message verbatim and unbounded
 * — an 8 MB answer was 8 MB in the model context, with nothing saying whose
 * words those were.
 */
export function upstreamText(value: unknown, max = 200): string {
  if (typeof value !== 'string') {
    return value === undefined || value === null
      ? '(none)'
      : `(non-text value of type ${typeof value})`;
  }
  const cleaned = redactUrl(value.replace(UNSAFE_CHARS, '').trim());
  const cut =
    cleaned.length > max ? `${cleaned.slice(0, max)}… (truncated)` : cleaned;
  return `(untrusted text from the service) ${cut}`;
}

export function sanitizeErrorBody(body: string): string {
  const trimmed = redactUrl(body.replace(UNSAFE_CHARS, '').trim());
  // Anything markup-shaped: a reverse proxy's error page or a WAF block page.
  // The check is deliberately loose — an XML declaration, a leading comment or
  // a doctype followed by a newline are all the same thing here.
  if (/^(<!doctype|<html[\s>]|<\?xml|<!--)/i.test(trimmed)) {
    return '(HTML error page omitted)';
  }
  if (trimmed.length > MAX_ERROR_BODY_LENGTH) {
    return `${trimmed.slice(0, MAX_ERROR_BODY_LENGTH)}… (truncated)`;
  }
  return trimmed;
}
