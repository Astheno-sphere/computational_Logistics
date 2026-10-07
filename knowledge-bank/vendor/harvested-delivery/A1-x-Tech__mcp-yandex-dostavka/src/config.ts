import type { DeliveryConfig } from "./types.js";

/** Default express (claims) contour host. */
export const DEFAULT_EXPRESS_BASE = "https://b2b.taxi.yandex.net";
/** Default platform (NDD) contour host; the test contour is b2b.taxi.tst.yandex.net. */
export const DEFAULT_PLATFORM_BASE = "https://b2b-authproxy.taxi.yandex.net";

/**
 * A malformed environment variable. Thrown instead of exiting on the spot so
 * index.ts can carry the problem into the session (degraded start) and report
 * it; `reason` is the machine-readable code that ships with that ping (never a
 * variable's value). A *missing* token is NOT a ConfigError — see loadConfig.
 */
export class ConfigError extends Error {
  readonly reason: string;

  constructor(message: string, reason: string) {
    super(message);
    this.name = "ConfigError";
    this.reason = reason;
  }
}

/**
 * Builds the client config from environment variables.
 *
 * Missing tokens are NOT an error here: the server starts anyway and the check
 * happens per contour at call time (CredentialsError in client.ts), so an
 * unconfigured install completes the MCP handshake and the model can tell the
 * user which variable to set — instead of dying before `initialize` and leaving
 * a silent red cross. There is no in-chat login for a Bearer token: the fix is
 * the operator setting the variables and restarting the server.
 *
 *   YANDEX_DELIVERY_TOKEN              Bearer token shared by both contours
 *   YANDEX_DELIVERY_EXPRESS_TOKEN      express-contour override (optional)
 *   YANDEX_DELIVERY_PLATFORM_TOKEN     platform-contour override (optional)
 *   YANDEX_DELIVERY_EXPRESS_BASE_URL   express API root override
 *   YANDEX_DELIVERY_PLATFORM_BASE_URL  platform API root override (test contour:
 *                                      https://b2b.taxi.tst.yandex.net)
 *   YANDEX_DELIVERY_LANG               Accept-Language (default ru)
 *   YANDEX_DELIVERY_TIMEOUT_MS         per-request timeout (default 60000)
 *   YANDEX_DELIVERY_MAX_RETRIES        transient-error retries (default 3)
 *
 * The common token fills whichever contour has no override; a contour left
 * without any token stays unset and rejects only its own calls (the express and
 * platform cabinets may issue different tokens, so a half-configured server
 * still serves the contour it has a token for).
 */
export function loadConfig(): DeliveryConfig {
  const common = process.env.YANDEX_DELIVERY_TOKEN;
  const expressToken = process.env.YANDEX_DELIVERY_EXPRESS_TOKEN || common;
  const platformToken = process.env.YANDEX_DELIVERY_PLATFORM_TOKEN || common;

  const timeoutMs = Number(process.env.YANDEX_DELIVERY_TIMEOUT_MS);
  const maxRetries = Number(process.env.YANDEX_DELIVERY_MAX_RETRIES);

  return {
    // An empty string reads as absent, never as an empty credential.
    expressToken: expressToken || undefined,
    platformToken: platformToken || undefined,
    expressBase: process.env.YANDEX_DELIVERY_EXPRESS_BASE_URL || DEFAULT_EXPRESS_BASE,
    platformBase: process.env.YANDEX_DELIVERY_PLATFORM_BASE_URL || DEFAULT_PLATFORM_BASE,
    lang: process.env.YANDEX_DELIVERY_LANG || "ru",
    timeoutMs: Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : 60_000,
    maxRetries: Number.isFinite(maxRetries) && maxRetries >= 0 ? maxRetries : 3,
  };
}
