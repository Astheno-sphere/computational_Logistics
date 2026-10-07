const BASE = (process.env.APOGEOAPI_BASE_URL ?? 'https://api.apogeoapi.com').replace(/\/+$/, '');
const TIMEOUT_MS = 15_000;

// Every tool only reads public reference data. Shared so each tool declares the
// same four hints: hosts use them to decide whether to ask before a call, and
// OpenAI's directory rejects tools where any of them is missing.
export const READ_ONLY = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
} as const;

function getKey(): string {
  const key = process.env.APOGEOAPI_KEY;
  if (!key) throw new Error('APOGEOAPI_KEY environment variable is required. Get a key at https://app.apogeoapi.com');
  return key;
}

/** Encodes a single path segment so user input can never change the requested route. */
export function seg(value: string | number): string {
  return encodeURIComponent(String(value).trim());
}

// What the assistant should tell the user, instead of a bare status code.
const HINTS: Record<number, string> = {
  401: 'The API key is missing or invalid. Check APOGEOAPI_KEY.',
  403: 'This endpoint is not included in the current plan. Countries and states are free; cities, global search, exchange rates and IP geolocation need the Basic plan or above (new accounts get them free for 14 days). Plans: https://apogeoapi.com/pricing',
  429: 'Rate limit or monthly quota reached for this plan. Wait and retry, or upgrade at https://apogeoapi.com/pricing',
};

export async function apiGet(path: string): Promise<unknown> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'X-API-Key': getKey(), Accept: 'application/json' },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (err) {
    const reason = err instanceof Error && err.name === 'TimeoutError' ? `no response after ${TIMEOUT_MS / 1000}s` : String(err);
    throw new Error(`ApogeoAPI request failed: ${reason}`);
  }
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    const hint = HINTS[res.status] ? ` ${HINTS[res.status]}` : '';
    throw new Error(`ApogeoAPI ${res.status}: ${body || res.statusText}.${hint}`);
  }
  return res.json();
}

export function asText(data: unknown) {
  return { content: [{ type: 'text' as const, text: JSON.stringify(data, null, 2) }] };
}
