import { SthanClient } from "@sthan/core";
import { resolveApiKey } from "./credentials.js";

/**
 * Build a SthanClient from the resolved API key (flag > env > file).
 * Exits with code 2 (auth error) if no key is available.
 * STHAN_API_URL overrides the base URL (test/local environments).
 */
export function getClient(flagKey?: string): SthanClient {
  const resolved = resolveApiKey(flagKey);
  if (!resolved) {
    console.error(
      "Not logged in. Run: sthan login --api-key sthan_...  (or set STHAN_API_KEY)"
    );
    process.exit(2);
  }
  return new SthanClient({
    apiKey: resolved.apiKey,
    baseUrl: process.env.STHAN_API_URL,
  });
}
