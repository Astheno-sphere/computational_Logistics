import { randomUUID } from "node:crypto";
import type { CancelState, DeliveryConfig } from "./types.js";
import { CredentialsError, DeliveryError } from "./types.js";

export type HttpMethod = "GET" | "POST";

/** Claims (express) path prefix on b2b.taxi.yandex.net. */
const PREFIX = "b2b/cargo/integration/v2/";

/**
 * Call-time text for a missing token — formerly the startup error that killed
 * the process before the MCP handshake, preserved verbatim (pinned in
 * client.test.ts). The message is the product: it is what the calling model
 * relays to the user, so it names the variable to set and says the server
 * needs a restart — there is no in-chat login for a Bearer token.
 */
const MISSING_TOKEN_MESSAGE =
  'YANGO_DELIVERY_TOKEN is required (OAuth token from the delivery cabinet, Integration tab -> "Get token").' +
  " This is not a network failure and retrying will not help: the operator must set this environment" +
  " variable in the MCP client's server config and restart the server — it is read only at startup.";

/** Query-string parameters; `undefined` values are dropped. */
export type Query = Record<string, string | number | boolean | undefined>;

export interface RequestOptions {
  query?: Query;
  body?: Record<string, unknown>;
  /**
   * Safe to retry on 5xx/network errors. GETs and side-effect-free POSTs
   * (check-price, claims/info, claims/search, points-eta, …) are;
   * state-changing POSTs are NOT — a 502 after the write commits would
   * duplicate the write. claims/create is the exception: its request_id
   * idempotency token makes a replay return the same claim. 429 is always
   * retried. Defaults to `method === "GET"`.
   */
  idempotent?: boolean;
}

export class DeliveryClient {
  private readonly base: string;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;
  private readonly retryBaseMs: number;

  constructor(private readonly config: DeliveryConfig) {
    this.base = normalizeBase(config.baseUrl);
    this.timeoutMs = config.timeoutMs ?? 60_000;
    this.maxRetries = config.maxRetries ?? 3;
    this.retryBaseMs = config.retryBaseMs ?? 500;
  }

  private headers(hasBody: boolean): Record<string, string> {
    const h: Record<string, string> = {
      Authorization: `Bearer ${this.config.token}`,
      // Documented as required on most claim method pages.
      "Accept-Language": this.config.lang,
    };
    if (hasBody) h["Content-Type"] = "application/json";
    return h;
  }

  /** Backoff before a retry: honors Retry-After when present, else exponential (capped at 30s). */
  private backoffMs(attempt: number, res?: Response): number {
    const retryAfter = res ? Number(res.headers.get("Retry-After")) : NaN;
    if (Number.isFinite(retryAfter) && retryAfter > 0) return Math.min(retryAfter, 30) * 1000;
    return Math.min(this.retryBaseMs * 2 ** attempt, 30_000);
  }

  /**
   * fetch with an AbortController timeout. Reads the response body inside the
   * guarded zone so the timeout also covers a slow or drip-feeding body, not just
   * the initial headers, and returns the text alongside the response.
   */
  private async fetchWithTimeout(
    url: string,
    init: RequestInit,
    label: string,
  ): Promise<{ res: Response; text: string }> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const res = await fetch(url, { ...init, signal: controller.signal });
      const text = await res.text();
      return { res, text };
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        throw new Error(`Request to "${label}" timed out after ${this.timeoutMs}ms`);
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  /**
   * Low-level request to a Yango Delivery path relative to the base
   * (e.g. "b2b/cargo/integration/v2/claims/info"). Retries 429 always; 5xx and
   * network errors/timeouts only for idempotent requests (see
   * {@link RequestOptions.idempotent}); any other non-2xx throws a
   * {@link DeliveryError}. Throws {@link CredentialsError} before any of that
   * when YANGO_DELIVERY_TOKEN is missing.
   */
  async request<T = unknown>(
    method: HttpMethod,
    path: string,
    opts: RequestOptions = {},
  ): Promise<T> {
    // A missing token is rejected before the request is built, retried or
    // sent: it is a configuration problem, not transport trouble, so it must
    // never enter the retry/backoff branch below — and fetch never fires
    // without auth (pinned in client.test.ts).
    if (!this.config.token) throw new CredentialsError(MISSING_TOKEN_MESSAGE);

    // Guard method !== "GET" keeps undici from crashing on a GET-with-body.
    const hasBody = opts.body !== undefined && method !== "GET";

    // Resolve the path against the base, then reject anything that escaped to
    // a foreign origin (an absolute "https://evil/x" or a "\\evil/x" slipped
    // through raw_request) so the Bearer token can never leak.
    const url = new URL(path.replace(/^\//, ""), this.base);
    if (url.origin !== new URL(this.base).origin) {
      throw new Error(`raw_request path must be a relative API path (resolved to foreign origin ${url.origin})`);
    }
    for (const [key, value] of Object.entries(opts.query ?? {})) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
    const target = url.toString();

    const idempotent = opts.idempotent ?? method === "GET";

    for (let attempt = 0; ; attempt++) {
      let res: Response;
      let text: string;
      try {
        ({ res, text } = await this.fetchWithTimeout(
          target,
          {
            method,
            headers: this.headers(hasBody),
            body: hasBody ? JSON.stringify(opts.body) : undefined,
          },
          path,
        ));
      } catch (err) {
        // Network error or timeout: retry idempotent requests with backoff; on the
        // last attempt (or a non-idempotent write) rethrow the original error.
        if (idempotent && attempt < this.maxRetries) {
          await delay(this.backoffMs(attempt));
          continue;
        }
        throw err;
      }

      const transient = res.status === 429 || (idempotent && res.status >= 500 && res.status < 600);
      if (transient && attempt < this.maxRetries) {
        await delay(this.backoffMs(attempt, res));
        continue;
      }

      let data: unknown = undefined;
      if (text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = text;
        }
      }

      if (!res.ok) throw new DeliveryError(res.status, data);
      return data as T;
    }
  }

  // --- Claim lifecycle --------------------------------------------------------

  /** Price estimation for a delivery without creating a claim. */
  async checkPrice(body: Record<string, unknown>): Promise<unknown> {
    return this.request("POST", PREFIX + "check-price", {
      body: compact(body),
      idempotent: true, // pure estimation, no side effects
    });
  }

  /**
   * Creates a claim. `request_id` is the idempotency token (a query parameter,
   * not a body field): a replay with the same token returns the same claim
   * instead of a duplicate, so a UUID is minted when the caller does not supply
   * one and the whole call is safe to retry.
   */
  async createClaim(p: { request_id?: string; body: Record<string, unknown> }): Promise<unknown> {
    return this.request("POST", PREFIX + "claims/create", {
      query: { request_id: p.request_id ?? randomUUID() },
      body: compact(p.body),
      idempotent: true,
    });
  }

  /** Full claim info: status, courier, pricing. The body is empty by contract. */
  async getClaim(claimId: string): Promise<unknown> {
    return this.request("POST", PREFIX + "claims/info", {
      query: { claim_id: claimId },
      idempotent: true, // side-effect-free read
    });
  }

  /** Confirms an estimated claim (starts the courier search). Not retried on 5xx. */
  async acceptClaim(p: { claim_id: string; version: number }): Promise<unknown> {
    return this.request("POST", PREFIX + "claims/accept", {
      query: { claim_id: p.claim_id },
      body: { version: p.version },
    });
  }

  /** Cancellation terms for a claim: free, paid or unavailable. */
  async cancelInfo(claimId: string): Promise<unknown> {
    return this.request("POST", PREFIX + "claims/cancel-info", {
      query: { claim_id: claimId },
      idempotent: true, // side-effect-free read
    });
  }

  /** Cancels a claim. `cancel_state` must come from {@link cancelInfo}. */
  async cancelClaim(p: { claim_id: string; version: number; cancel_state: CancelState }): Promise<unknown> {
    return this.request("POST", PREFIX + "claims/cancel", {
      query: { claim_id: p.claim_id },
      body: { version: p.version, cancel_state: p.cancel_state },
    });
  }

  /** Searches claims by filters with offset/limit or cursor pagination. */
  async searchClaims(filters: Record<string, unknown>): Promise<unknown> {
    return this.request("POST", PREFIX + "claims/search", {
      body: compact(filters),
      idempotent: true, // side-effect-free read
    });
  }

  // --- Tracking & contact -----------------------------------------------------

  /** Live courier position for an active claim. */
  async performerPosition(claimId: string): Promise<unknown> {
    return this.request("GET", PREFIX + "claims/performer-position", {
      query: { claim_id: claimId },
    });
  }

  /** Public tracking links (sharing_link per destination point). */
  async trackingLinks(claimId: string): Promise<unknown> {
    return this.request("GET", PREFIX + "claims/tracking-links", {
      query: { claim_id: claimId },
    });
  }

  /** Expected arrival times per route point. The body is empty by contract. */
  async pointsEta(claimId: string): Promise<unknown> {
    return this.request("POST", PREFIX + "claims/points-eta", {
      query: { claim_id: claimId },
      idempotent: true, // side-effect-free read
    });
  }

  /** Temporary forwarded phone number to call the courier. */
  async courierPhone(p: { claim_id: string; point_id?: number }): Promise<unknown> {
    return this.request("POST", PREFIX + "driver-voiceforwarding", {
      body: compact({ claim_id: p.claim_id, point_id: p.point_id }),
      // Fetching a forwarding number does not change the claim; a replay just
      // returns a (possibly fresh) number, so retrying on 5xx is safe.
      idempotent: true,
    });
  }

  /** Pickup/delivery confirmation code for the current point (when one applies). */
  async confirmationCode(claimId: string): Promise<unknown> {
    // Note: claim_id rides in the BODY here, not the query (per the method page).
    return this.request("POST", PREFIX + "claims/confirmation_code", {
      body: { claim_id: claimId },
      idempotent: true, // side-effect-free read
    });
  }
}

function normalizeBase(base: string): string {
  return base.endsWith("/") ? base : base + "/";
}

/** Drops keys whose value is `undefined` so they are not sent to the API. */
function compact<T extends Record<string, unknown>>(obj: T): T {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined)) as T;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
