import { randomUUID } from "node:crypto";
import type { CancelState, DeliveryConfig } from "./types.js";
import { CredentialsError, DeliveryError } from "./types.js";

export type HttpMethod = "GET" | "POST";

/**
 * The two independent halves of the Yandex Delivery B2B API. Each has its own
 * host, path prefix and (potentially) its own Bearer token.
 */
export type Contour = "express" | "platform";

/** Express (claims) path prefix on b2b.taxi.yandex.net. */
const EXPRESS = "b2b/cargo/integration/v2/";
/** Platform (NDD) path prefix on b2b-authproxy.taxi.yandex.net. */
const PLATFORM = "api/b2b/platform/";

/** Query-string parameters; `undefined` values are dropped. */
export type Query = Record<string, string | number | boolean | undefined>;

export interface RequestOptions {
  query?: Query;
  body?: Record<string, unknown>;
  /**
   * Safe to retry on 5xx/network errors. GETs and side-effect-free POSTs
   * (check-price, claims/info, claims/search, pickup-points/list, …) are;
   * state-changing POSTs are NOT — a 502 after the write commits would
   * duplicate the write. claims/create is the exception: its request_id
   * idempotency token makes a replay return the same claim. 429 is always
   * retried. Defaults to `method === "GET"`.
   */
  idempotent?: boolean;
}

/**
 * Call-time texts for a missing token — formerly the startup errors that killed
 * the process before the MCP handshake, preserved verbatim (pinned in
 * client.test.ts). The message is the product: it is what the calling model
 * relays to the user, so it names the variables to set and says the server
 * needs a restart — there is no in-chat login for a Bearer token.
 */
const MISSING_TOKEN_TEXT =
  "YANDEX_DELIVERY_TOKEN is required (Bearer token from dostavka.yandex.ru → «Интеграции» → «Получить токен»).";
const MISSING_EXPRESS_TOKEN_TEXT =
  "Express-contour token is missing: set YANDEX_DELIVERY_TOKEN (shared) or YANDEX_DELIVERY_EXPRESS_TOKEN.";
const MISSING_PLATFORM_TOKEN_TEXT =
  "Platform-contour token is missing: set YANDEX_DELIVERY_TOKEN (shared) or YANDEX_DELIVERY_PLATFORM_TOKEN.";
const RESTART_HINT =
  " This is not a network failure and retrying will not help: the operator must set these " +
  "environment variables in the MCP client's server config and restart the server — they are " +
  "read only at startup.";

export class DeliveryClient {
  private readonly bases: Record<Contour, string>;
  private readonly tokens: Record<Contour, string | undefined>;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;
  private readonly retryBaseMs: number;

  constructor(private readonly config: DeliveryConfig) {
    this.bases = {
      express: normalizeBase(config.expressBase),
      platform: normalizeBase(config.platformBase),
    };
    this.tokens = {
      express: config.expressToken,
      platform: config.platformToken,
    };
    this.timeoutMs = config.timeoutMs ?? 60_000;
    this.maxRetries = config.maxRetries ?? 3;
    this.retryBaseMs = config.retryBaseMs ?? 500;
  }

  /**
   * The Bearer token serving `contour`, or a CredentialsError naming the fix.
   * The check is per contour and per call: a half-configured server keeps
   * serving the contour it has a token for, and only the bare contour's calls
   * fail. With no tokens at all the shared-variable message wins — that is
   * what an unconfigured install should be told to set first.
   */
  private token(contour: Contour): string {
    const token = this.tokens[contour];
    if (token) return token;
    const neither = !this.tokens.express && !this.tokens.platform;
    const what = neither
      ? MISSING_TOKEN_TEXT
      : contour === "express"
        ? MISSING_EXPRESS_TOKEN_TEXT
        : MISSING_PLATFORM_TOKEN_TEXT;
    throw new CredentialsError(what + RESTART_HINT);
  }

  private headers(token: string, hasBody: boolean): Record<string, string> {
    const h: Record<string, string> = {
      Authorization: `Bearer ${token}`,
      // Required by the express methods; harmless for the platform ones.
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
   * Low-level request to a Yandex Delivery path relative to the contour's base
   * (e.g. "b2b/cargo/integration/v2/claims/info" or "api/b2b/platform/request/info").
   * Throws {@link CredentialsError} before any network I/O when the contour
   * serving the call has no Bearer token. Retries 429 always; 5xx and network
   * errors/timeouts only for idempotent requests (see
   * {@link RequestOptions.idempotent}); any other non-2xx throws a
   * {@link DeliveryError}.
   */
  async request<T = unknown>(
    contour: Contour,
    method: HttpMethod,
    path: string,
    opts: RequestOptions = {},
  ): Promise<T> {
    // A missing token is rejected before the request is built, retried or
    // sent: it is a configuration problem, not transport trouble, so it must
    // never enter the retry/backoff loop below — and fetch never fires
    // without auth (pinned in client.test.ts).
    const token = this.token(contour);

    // Guard method !== "GET" keeps undici from crashing on a GET-with-body.
    const hasBody = opts.body !== undefined && method !== "GET";

    // Resolve the path against the contour's base, then reject anything that
    // escaped to a foreign origin (an absolute "https://evil/x" or a "\\evil/x"
    // slipped through raw_request) so the Bearer token can never leak.
    const base = this.bases[contour];
    const url = new URL(path.replace(/^\//, ""), base);
    if (url.origin !== new URL(base).origin) {
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
            headers: this.headers(token, hasBody),
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

  // --- Express (claims) contour ---------------------------------------------

  /** Price estimation for an express delivery without creating a claim. */
  async checkPrice(body: Record<string, unknown>): Promise<unknown> {
    return this.request("express", "POST", EXPRESS + "check-price", {
      body: compact(body),
      idempotent: true, // pure estimation, no side effects
    });
  }

  /**
   * Creates an express claim. `request_id` is the idempotency token (a query
   * parameter, not a body field): a replay with the same token returns the same
   * claim instead of a duplicate, so a UUID is minted when the caller does not
   * supply one and the whole call is safe to retry.
   */
  async createClaim(p: { request_id?: string; body: Record<string, unknown> }): Promise<unknown> {
    return this.request("express", "POST", EXPRESS + "claims/create", {
      query: { request_id: p.request_id ?? randomUUID() },
      body: compact(p.body),
      idempotent: true,
    });
  }

  /** Full claim info: status, courier, pricing. The body is empty by contract. */
  async getClaim(claimId: string): Promise<unknown> {
    return this.request("express", "POST", EXPRESS + "claims/info", {
      query: { claim_id: claimId },
      idempotent: true, // side-effect-free read
    });
  }

  /** Confirms an estimated claim (starts the courier search). Not retried on 5xx. */
  async acceptClaim(p: { claim_id: string; version: number }): Promise<unknown> {
    return this.request("express", "POST", EXPRESS + "claims/accept", {
      query: { claim_id: p.claim_id },
      body: { version: p.version },
    });
  }

  /** Cancellation terms for a claim: free, paid or unavailable. */
  async cancelInfo(claimId: string): Promise<unknown> {
    return this.request("express", "POST", EXPRESS + "claims/cancel-info", {
      query: { claim_id: claimId },
      idempotent: true, // side-effect-free read
    });
  }

  /** Cancels a claim. `cancel_state` must come from {@link cancelInfo}. */
  async cancelClaim(p: { claim_id: string; version: number; cancel_state: CancelState }): Promise<unknown> {
    return this.request("express", "POST", EXPRESS + "claims/cancel", {
      query: { claim_id: p.claim_id },
      body: { version: p.version, cancel_state: p.cancel_state },
    });
  }

  /** Searches claims by filters with offset/limit or cursor pagination. */
  async searchClaims(filters: Record<string, unknown>): Promise<unknown> {
    return this.request("express", "POST", EXPRESS + "claims/search", {
      body: compact(filters),
      idempotent: true, // side-effect-free read
    });
  }

  /** Live courier position for an active claim. */
  async performerPosition(claimId: string): Promise<unknown> {
    return this.request("express", "GET", EXPRESS + "claims/performer-position", {
      query: { claim_id: claimId },
    });
  }

  /** Public tracking links (sharing_link per destination point). */
  async trackingLinks(claimId: string): Promise<unknown> {
    return this.request("express", "GET", EXPRESS + "claims/tracking-links", {
      query: { claim_id: claimId },
    });
  }

  // --- Platform (NDD) contour ------------------------------------------------

  /** Pickup points, parcel lockers and drop-off warehouses, filtered. */
  async listPickupPoints(filters: Record<string, unknown>): Promise<unknown> {
    return this.request("platform", "POST", PLATFORM + "pickup-points/list", {
      body: compact(filters),
      idempotent: true, // side-effect-free read
    });
  }

  /** Delivery options (offers) for an NDD order; each offer lives until expires_at. */
  async createOffers(body: Record<string, unknown>): Promise<unknown> {
    return this.request("platform", "POST", PLATFORM + "offers/create", {
      body: compact(body),
      // A replayed calculation only re-issues offers; no order is created.
      idempotent: true,
    });
  }

  /** Books an offer — creates the order. Not retried on 5xx (a real write). */
  async confirmOffer(offerId: string): Promise<unknown> {
    return this.request("platform", "POST", PLATFORM + "offers/confirm", {
      body: { offer_id: offerId },
    });
  }

  /** NDD order info: current status, contents, recipient. */
  async getRequest(p: { request_id: string; request_code?: string; slim?: boolean }): Promise<unknown> {
    return this.request("platform", "GET", PLATFORM + "request/info", {
      query: { request_id: p.request_id, request_code: p.request_code, slim: p.slim },
    });
  }

  /** Status-change history of an NDD order. */
  async requestHistory(requestId: string): Promise<unknown> {
    return this.request("platform", "GET", PLATFORM + "request/history", {
      query: { request_id: requestId },
    });
  }

  /** Cancels an NDD order. Not retried on 5xx (a real write). */
  async cancelRequest(requestId: string): Promise<unknown> {
    return this.request("platform", "POST", PLATFORM + "request/cancel", {
      body: { request_id: requestId },
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
