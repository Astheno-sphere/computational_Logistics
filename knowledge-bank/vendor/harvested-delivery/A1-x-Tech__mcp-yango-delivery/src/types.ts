/**
 * The server talks to the Yango Delivery B2B API — the international brand of
 * Yandex Delivery. Only the express (same-day / on-demand courier claims)
 * contour exists in the international documentation: https://b2b.taxi.yandex.net,
 * paths under /b2b/cargo/integration/v2/*. The platform (NDD / pickup-point)
 * contour and the offers/calculate pricing method are Russia-only and are
 * deliberately not covered here; check-price is the international pricing path.
 *
 * Auth is `Authorization: Bearer <token>`; the token is issued in the delivery
 * personal account (Integration tab -> "Get token"), never expires but is
 * invalidated when the account password changes.
 */

/** Express delivery class (wire values are identical to the normalized ones). */
export type TaxiClass = "courier" | "express" | "cargo";

/** Cargo vehicle body type for taxi_class=cargo. */
export type CargoType = "van" | "lcv_m" | "lcv_l";

/** Cancellation mode reported by claims/cancel-info and sent to claims/cancel. */
export type CancelState = "free" | "paid";

export interface DeliveryConfig {
  /**
   * Bearer token for the claims API. Treated as a secret. Absent when
   * YANGO_DELIVERY_TOKEN is not set — the server still starts (degraded) and
   * the client raises {@link CredentialsError} at call time.
   */
  token?: string;
  /** API root. Defaults to https://b2b.taxi.yandex.net. */
  baseUrl: string;
  /** Accept-Language header value (required by most claim methods). */
  lang: string;
  /** Per-request timeout in milliseconds. Defaults to 60_000. */
  timeoutMs?: number;
  /** Max retries for transient errors (429 rate limit, 5xx). Defaults to 3. */
  maxRetries?: number;
  /** Base backoff in milliseconds, doubled each retry. Defaults to 500. */
  retryBaseMs?: number;
}

/**
 * Raised when a tool is called while YANGO_DELIVERY_TOKEN is missing. The
 * message is the whole point of the class: it is the only text the calling
 * model reads and relays, so it names the variable to set (and that the server
 * needs a restart) instead of describing the failure. The client throws it
 * before building the request — a missing credential is a configuration
 * problem, not transport trouble, so it must never enter the retry/backoff
 * branch or reach fetch.
 */
export class CredentialsError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CredentialsError";
  }
}

/**
 * The API reports failures as a non-2xx HTTP status with a JSON body of
 * `{ code, message }` (e.g. `not_found`, `inappropriate_status`,
 * `estimating.cant_construct_route`). The parsed body is kept alongside the
 * status and a short readable message is derived. Note: claims/info and
 * claims/create can additionally embed estimation errors as an
 * `error_messages` array inside a 200 response — those pass through to the
 * caller untouched.
 */
export class DeliveryError extends Error {
  readonly status: number;
  readonly body?: unknown;

  constructor(status: number, body: unknown) {
    super(`HTTP ${status}: ${formatErrorBody(body)}`);
    this.name = "DeliveryError";
    this.status = status;
    this.body = body;
  }
}

/** Turns a parsed Yango Delivery error body into a short, readable message. */
function formatErrorBody(body: unknown): string {
  if (body == null) return "(no body)";
  if (typeof body === "string") return body.slice(0, 500);
  if (typeof body !== "object") return String(body);
  const obj = body as Record<string, unknown>;

  // The common shape: { code: "not_found", message: "..." }
  if (typeof obj.message === "string") {
    const code = obj.code !== undefined ? `[${String(obj.code)}] ` : "";
    return `${code}${obj.message}`.slice(0, 500);
  }

  // Some responses carry an array of { code, message } items instead.
  if (Array.isArray(obj.error_messages)) {
    return JSON.stringify(obj.error_messages).slice(0, 500);
  }

  return JSON.stringify(obj).slice(0, 500);
}
