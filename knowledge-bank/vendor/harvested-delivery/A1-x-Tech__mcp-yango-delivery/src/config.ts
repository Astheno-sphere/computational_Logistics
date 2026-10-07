import type { DeliveryConfig } from "./types.js";

/** Default API host — the EN docs use the same host for Russia and other countries. */
export const DEFAULT_BASE = "https://b2b.taxi.yandex.net";

/**
 * A malformed environment variable. Thrown instead of exiting on the spot so
 * index.ts can carry the problem into the session (degraded start) and report
 * it; `reason` is the machine-readable code that ships with that ping (never a
 * variable's value). A *missing* variable is NOT a ConfigError — see loadConfig.
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
 * A missing YANGO_DELIVERY_TOKEN is NOT an error here: the server starts
 * anyway and the check happens per tool call (CredentialsError in client.ts),
 * so an unconfigured install completes the MCP handshake and the model can
 * tell the user which variable to set — instead of dying before `initialize`
 * and leaving a dead server with no reason. There is no in-chat login for a
 * Bearer token: the fix is the operator setting the variable and restarting
 * the server.
 *
 *   YANGO_DELIVERY_TOKEN        Bearer token
 *   YANGO_DELIVERY_BASE_URL     API root override
 *   YANGO_DELIVERY_LANG         Accept-Language (default en)
 *   YANGO_DELIVERY_TIMEOUT_MS   per-request timeout (default 60000)
 *   YANGO_DELIVERY_MAX_RETRIES  transient-error retries (default 3)
 */
export function loadConfig(): DeliveryConfig {
  const timeoutMs = Number(process.env.YANGO_DELIVERY_TIMEOUT_MS);
  const maxRetries = Number(process.env.YANGO_DELIVERY_MAX_RETRIES);

  return {
    // An empty string reads as absent, never as an empty credential.
    token: process.env.YANGO_DELIVERY_TOKEN || undefined,
    baseUrl: process.env.YANGO_DELIVERY_BASE_URL || DEFAULT_BASE,
    lang: process.env.YANGO_DELIVERY_LANG || "en",
    timeoutMs: Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : 60_000,
    maxRetries: Number.isFinite(maxRetries) && maxRetries >= 0 ? maxRetries : 3,
  };
}
