// Default to the canonical public host. The bare App Hosting URL
// (...hosted.app) also serves the API, but it is not the domain we publish and
// it moves with the backend, so it is a poor default for an installed client.
// Override with ADDRESSINTEL_API_BASE for local or staging work.
const API_BASE = process.env.ADDRESSINTEL_API_BASE || 'https://addressintel.co/api';
const API_KEY = process.env.ADDRESSINTEL_API_KEY;

function authHeaders(): Record<string, string> {
    // An unset key falls back to the public demo tier (10 req/min, 5 rows) so
    // the server is useful the moment it is installed. Sending nothing at all
    // makes every endpoint 401, which is what the previous version did.
    return {
        'Content-Type': 'application/json',
        'x-api-key': API_KEY || 'demo',
    };
}

type ParamValue = string | number | boolean | undefined;

function withParams(path: string, params: Record<string, ParamValue>): URL {
    const url = new URL(`${API_BASE}${path}`);
    for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== '') url.searchParams.append(key, String(value));
    }
    return url;
}

async function get(url: URL, { nullOn404 = false } = {}) {
    const res = await fetch(url.toString(), { headers: authHeaders() });
    if (!res.ok) {
        if (nullOn404 && res.status === 404) return null;
        // The API returns a readable `error` in its failure envelope. Surfacing
        // it beats a bare status line: it is what tells the agent whether to
        // narrow the query, back off, or ask the user for a key.
        let detail = res.statusText;
        try {
            const body = await res.json();
            if (body?.error) detail = body.error;
        } catch {
            // Non-JSON error body; the status line is all we have.
        }
        throw new Error(`AddressIntel API error (${res.status}): ${detail}`);
    }
    return await res.json();
}

export async function fetchMarketSignals(params: { market?: string, city?: string, address?: string, limit?: number }) {
    return await get(withParams('/v1/market-signals', params));
}

export async function fetchPropertyIntelligence(id: string) {
    return await get(new URL(`${API_BASE}/v1/properties/${encodeURIComponent(id)}`), { nullOn404: true });
}

export async function fetchPermits(params: { city?: string, q?: string, minValuation?: number, limit?: number, offset?: number }) {
    return await get(withParams('/v1/permits', params));
}

export async function fetchSb9Inventory(params: { status?: string, minUnits?: number, excludeBlockers?: boolean, limit?: number }) {
    return await get(withParams('/v1/sb9-inventory', params));
}

export async function fetchAduLeads(params: { minScore?: number, excludeBlockers?: boolean, limit?: number }) {
    return await get(withParams('/v1/adu-leads', params));
}

export async function fetchRedevelopmentLeads(params: { minScore?: number, class?: string, excludeBlockers?: boolean, limit?: number }) {
    return await get(withParams('/v1/redevelopment-leads', params));
}
