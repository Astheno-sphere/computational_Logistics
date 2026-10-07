import { homedir } from "node:os";
import { join } from "node:path";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

export interface Credentials {
  apiKey: string;
}

export type ApiKeySource = "flag" | "env" | "file";

export interface ResolvedApiKey {
  apiKey: string;
  source: ApiKeySource;
}

const CONFIG_DIR = join(homedir(), ".sthan");
const CREDENTIALS_FILE = join(CONFIG_DIR, "credentials.json");

/** Read the stored credentials file, or null if it doesn't exist / is unreadable. */
export function loadCredentials(): Credentials | null {
  try {
    const raw = readFileSync(CREDENTIALS_FILE, "utf8");
    const parsed = JSON.parse(raw) as Partial<Credentials>;
    return parsed.apiKey ? { apiKey: parsed.apiKey } : null;
  } catch {
    return null;
  }
}

/** Persist the API key to ~/.sthan/credentials.json (owner-only perms where supported). */
export function saveApiKey(apiKey: string): string {
  mkdirSync(CONFIG_DIR, { recursive: true });
  writeFileSync(CREDENTIALS_FILE, JSON.stringify({ apiKey }, null, 2), {
    mode: 0o600,
  });
  return CREDENTIALS_FILE;
}

/**
 * Resolve the API key by precedence: explicit flag > STHAN_API_KEY env > stored file.
 * Returns null if none is found.
 */
export function resolveApiKey(flagKey?: string): ResolvedApiKey | null {
  if (flagKey) return { apiKey: flagKey, source: "flag" };
  const env = process.env.STHAN_API_KEY;
  if (env) return { apiKey: env, source: "env" };
  const file = loadCredentials();
  if (file) return { apiKey: file.apiKey, source: "file" };
  return null;
}

/** Mask a key for display: keep the prefix + last 4 chars. */
export function maskApiKey(apiKey: string): string {
  if (apiKey.length <= 12) return "****";
  return `${apiKey.slice(0, 12)}…${apiKey.slice(-4)}`;
}

export { CREDENTIALS_FILE };
