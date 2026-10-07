import { SthanApiError } from "@sthan/core";

/** Case-insensitive field lookup — survives PascalCase vs camelCase API JSON. */
export function pick(obj: Record<string, unknown>, key: string): unknown {
  if (key in obj) return obj[key];
  const lower = key.toLowerCase();
  for (const k of Object.keys(obj)) {
    if (k.toLowerCase() === lower) return obj[k];
  }
  return undefined;
}

/** pick() coerced to a trimmed string ("" when missing/null). */
export function str(obj: Record<string, unknown>, key: string): string {
  const v = pick(obj, key);
  return v == null ? "" : String(v).trim();
}

/** pick() a nested object (e.g. geocode's `location`/`accuracy`), or undefined. */
export function obj(
  o: Record<string, unknown>,
  key: string
): Record<string, unknown> | undefined {
  const v = pick(o, key);
  return v && typeof v === "object" ? (v as Record<string, unknown>) : undefined;
}

/** Print a label/value list, skipping empty values. */
export function printFields(fields: Array<[string, string]>): void {
  for (const [label, value] of fields) {
    if (value) console.log(`  ${label}: ${value}`);
  }
}

/**
 * Print an error and exit with the conventional code:
 *   2 = auth, 3 = authorization/rate-limit, 5 = network, 1 = general.
 * Never returns.
 */
export function die(e: unknown): never {
  if (e instanceof SthanApiError) {
    console.error(`Error (${e.statusCode}): ${e.message}`);
    const code =
      e.statusCode === 401 ? 2 : e.statusCode === 403 || e.statusCode === 429 ? 3 : 1;
    process.exit(code);
  }
  const msg = e instanceof Error ? e.message : String(e);
  console.error(`Error: ${msg}`);
  process.exit(5);
}
