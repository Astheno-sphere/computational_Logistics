// ─────────────────────────────────────────────────────────────────────────────
// Zornade MCP - definizioni condivise dei tool (HTTP + stdio)
//
// Modulo senza side effect. buildTools() costruisce i sei strumenti MCP a
// partire da una chiave API. Usato da:
//   - index.ts  Supabase Edge Function, mcp-lite streamable HTTP
//   - stdio.ts  container Docker (check Glama), JSON-RPC su stdin/stdout
// ─────────────────────────────────────────────────────────────────────────────

import { z } from 'npm:zod@4.1.12';
import { createClient, type SupabaseClient } from 'npm:@supabase/supabase-js@2.49.8';

const ZORNADE_BASE = 'https://api.zornade.com/api/v2';

export interface ToolTextResult {
  content: Array<{ type: 'text'; text: string }>;
  isError?: boolean;
}

export interface ToolDef {
  name: string;
  description: string;
  inputSchema: z.ZodTypeAny;
  handler: (args: Record<string, unknown>) => Promise<ToolTextResult>;
}

interface ApiErrorBody {
  error?: string;
  message?: string;
}

export function extractApiKey(req: Request): string | null {
  const header = req.headers.get('x-api-key');
  if (header?.startsWith('zrn_')) return header;
  const auth = req.headers.get('authorization');
  if (auth?.startsWith('Bearer ')) {
    const token = auth.slice(7).trim();
    if (token.startsWith('zrn_')) return token;
  }
  const param = new URL(req.url).searchParams.get('api_key');
  if (param?.startsWith('zrn_')) return param;
  // Fallback: chiave di default dall'ambiente (self-hosting / check automatici
  // tipo Glama, che iniettano ZORNADE_API_KEY come placeholder).
  const envKey = Deno.env.get('ZORNADE_API_KEY');
  if (envKey?.startsWith('zrn_')) return envKey;
  return null;
}

// ─── Logging usage (tabella mcp_usage, fire-and-forget) ─────────────────────

let _usageDb: SupabaseClient | null = null;

function usageDb(): SupabaseClient | null {
  const url = Deno.env.get('SUPABASE_URL');
  const key = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
  if (!url || !key) return null;
  if (!_usageDb) {
    _usageDb = createClient(url, key, { auth: { persistSession: false } });
  }
  return _usageDb;
}

export function logMcpUsage(entry: {
  tool: string;
  status?: string;
  statusCode?: number | null;
  durationMs?: number | null;
  tokenPrefix?: string | null;
  client?: string | null;
}): void {
  const db = usageDb();
  if (!db) return;
  void (async () => {
    try {
      const r = await db.from('mcp_usage').insert({
        tool: entry.tool,
        status: entry.status ?? 'ok',
        status_code: entry.statusCode ?? null,
        duration_ms: entry.durationMs ?? null,
        token_prefix: entry.tokenPrefix ?? null,
        client: entry.client ?? null,
      });
      if (r.error) console.error('mcp_usage insert failed:', r.error.message);
    } catch {
      // Il logging non deve mai interferire con la risposta MCP.
    }
  })();
}

// ─── Traduzione etichette in inglese per il livello MCP ──────────────────
//
// L'API v2 espone quasi tutti i nomi di campo in inglese. Le poche eccezioni
// italiane vengono tradotte qui, SOLO per le risposte MCP: l'API REST resta
// invariata per i client esistenti. I valori restano in italiano dove sono
// nomi propri (comuni, strade, regioni) o termini catastali ufficiali (foglio).

const KEY_RENAMES: Record<string, string> = {
  sezione_urbana: 'urban_section',
  comune_code: 'municipality_code',
};

const VALUE_TRANSLATIONS: Record<string, Record<string, string>> = {
  risk_label: {
    trascurabile: 'negligible',
    basso: 'low',
    medio: 'medium',
    alto: 'high',
    elevato: 'very high',
  },
  direction: {
    stabile: 'stable',
    subsidenza: 'subsidence',
    sollevamento: 'uplift',
  },
};

function translateToEnglish(node: unknown): void {
  if (Array.isArray(node)) {
    for (const item of node) translateToEnglish(item);
    return;
  }
  if (node && typeof node === 'object') {
    const obj = node as Record<string, unknown>;
    for (const key of Object.keys(obj)) {
      const value = obj[key];
      if (typeof value === 'string') {
        const map = VALUE_TRANSLATIONS[key];
        if (map && map[value] !== undefined) obj[key] = map[value];
      } else {
        translateToEnglish(value);
      }
      if (key in KEY_RENAMES) {
        obj[KEY_RENAMES[key]] = value;
        delete obj[key];
      }
    }
  }
}

async function callApi(apiKey: string | null, endpoint: string, toolName: string): Promise<string> {
  const started = Date.now();
  if (!apiKey) {
    logMcpUsage({ tool: toolName, status: 'error', durationMs: Date.now() - started });
    return 'ERROR: Zornade API key missing. Send it as x-api-key header, Authorization: Bearer header, or ?api_key= query parameter. Free keys: https://app.zornade.com/api';
  }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 20000);
  try {
    const r = await fetch(`${ZORNADE_BASE}/${endpoint}`, {
      headers: { 'x-api-key': apiKey, Accept: 'application/json' },
      signal: ctrl.signal,
    });
    const body = (await r.json()) as (Record<string, unknown> & ApiErrorBody) | null;
    const ms = Date.now() - started;
    logMcpUsage({
      tool: toolName,
      status: r.ok ? 'ok' : 'error',
      statusCode: r.status,
      durationMs: ms,
      tokenPrefix: apiKey.slice(0, 8),
    });
    if (!r.ok) {
      const err = (body ?? {}) as ApiErrorBody;
      return `ERROR (HTTP ${r.status}): ${err.message ?? err.error ?? 'unknown error'}`;
    }
    // Il dettaglio particella include la geometria GeoJSON completa: la
    // rimuoviamo per tenere il contesto LLM leggero (i token costano).
    const data = (body as { data?: { geometry?: unknown } }).data;
    if (data && 'geometry' in data) delete data.geometry;
    translateToEnglish(body);
    return JSON.stringify(body, null, 2);
  } catch (e) {
    logMcpUsage({
      tool: toolName,
      status: 'error',
      durationMs: Date.now() - started,
      tokenPrefix: apiKey.slice(0, 8),
    });
    if ((e as Error).name === 'AbortError') {
      return 'ERROR: Zornade API call timed out after 20 seconds.';
    }
    return `ERROR: API call failed (${(e as Error).message})`;
  } finally {
    clearTimeout(timer);
  }
}

export function buildTools(apiKey: string | null): ToolDef[] {
  const textResult = (out: string): ToolTextResult => ({
    content: [{ type: 'text', text: out }],
    isError: out.startsWith('ERROR'),
  });

  return [
    {
      name: 'zornade_geocode_search',
      description:
        'Forward geocoding for Italian addresses. Searches the ANNCSU street archive ' +
        '(18.7+ million addresses) by street name and optional municipality. ' +
        'Returns matches with WGS84 coordinates, postal code, municipality, province and region. ' +
        'Does NOT find points of interest: search by street name instead.',
      inputSchema: z.object({
        q: z.string().describe('Street name or search text, min 2 chars. Example: "Via del Corso"'),
        city: z.string().optional().describe('Municipality name filter. Example: "Roma"'),
        limit: z.number().int().min(1).max(50).optional().describe('Max results, default 10'),
      }),
      handler: async (raw: Record<string, unknown>) => {
        const args = raw as { q: string; city?: string; limit?: number };
        const p = new URLSearchParams();
        p.set('q', args.q);
        if (args.city) p.set('city', args.city);
        p.set('limit', String(args.limit ?? 10));
        return textResult(await callApi(apiKey, `geocode/search?${p.toString()}`, 'zornade_geocode_search'));
      },
    },
    {
      name: 'zornade_geocode_reverse',
      description:
        'Reverse geocoding: find Italian addresses near WGS84 coordinates. ' +
        'Returns the closest ANNCSU addresses with distance in meters.',
      inputSchema: z.object({
        lat: z.number().min(35.5).max(47.5).describe('Latitude WGS84, Italy bounds 35.5-47.5'),
        lng: z.number().min(6.0).max(19.0).describe('Longitude WGS84, Italy bounds 6.0-19.0'),
        radius: z.number().int().min(1).max(500).optional().describe('Search radius in meters, default 100, max 500'),
        limit: z.number().int().min(1).max(20).optional().describe('Max results, default 5'),
      }),
      handler: async (raw: Record<string, unknown>) => {
        const args = raw as { lat: number; lng: number; radius?: number; limit?: number };
        const p = new URLSearchParams();
        p.set('lat', String(args.lat));
        p.set('lng', String(args.lng));
        p.set('radius', String(args.radius ?? 100));
        p.set('limit', String(args.limit ?? 5));
        return textResult(await callApi(apiKey, `geocode/reverse?${p.toString()}`, 'zornade_geocode_reverse'));
      },
    },
    {
      name: 'zornade_parcel_by_id',
      description:
        'Enriched cadastral parcel profile by FID or GML ID. ' +
        'Returns municipality, area, cadastral reference, and the requested data sections ' +
        '(risk, subsidence, terrain, buildings, economics, demographics, valuation, ' +
        'valuation_history, solar, POI, etc.). Geometry is omitted to keep the reply compact.',
      inputSchema: z.object({
        fid: z.string().describe('Parcel FID number (example "28009975") or GML ID'),
        include: z
          .string()
          .optional()
          .describe(
            'Comma-separated sections: risk,subsidence,terrain,population,buildings,economics,' +
              'demographics,land_cover,land_use,valuation,valuation_history,coastal_erosion,' +
              'cultural_heritage,poi,solar,nightlights. Default: risk,economics,solar,valuation',
          ),
      }),
      handler: async (raw: Record<string, unknown>) => {
        const args = raw as { fid: string; include?: string };
        const include = args.include ?? 'risk,economics,solar,valuation';
        return textResult(
          await callApi(apiKey, `parcels/${encodeURIComponent(args.fid)}?include=${encodeURIComponent(include)}`, 'zornade_parcel_by_id'),
        );
      },
    },
    {
      name: 'zornade_parcel_locate',
      description:
        'Find cadastral parcels by coordinates or bounding box. Three modes: ' +
        'single point (lat+lng), multiple points (points="lat,lng;lat,lng", max 10), ' +
        'or bounding box (bbox="minLng,minLat,maxLng,maxLat", max 0.05 degrees per side). ' +
        'Returns matching parcels with FID, municipality and centroid.',
      inputSchema: z.object({
        lat: z.number().optional().describe('Latitude for single-point mode'),
        lng: z.number().optional().describe('Longitude for single-point mode'),
        points: z
          .string()
          .optional()
          .describe('Multiple points as "lat,lng;lat,lng", max 10 pairs'),
        bbox: z
          .string()
          .optional()
          .describe('Bounding box as "minLng,minLat,maxLng,maxLat", max 0.05 degrees per side'),
        limit: z.number().int().min(1).max(200).optional().describe('Max results, default 50'),
      }),
      handler: async (raw: Record<string, unknown>) => {
        const args = raw as {
          lat?: number;
          lng?: number;
          points?: string;
          bbox?: string;
          limit?: number;
        };
        const p = new URLSearchParams();
        if (args.bbox) {
          p.set('bbox', args.bbox);
        } else if (args.points) {
          p.set('points', args.points);
        } else if (args.lat != null && args.lng != null) {
          p.set('lat', String(args.lat));
          p.set('lng', String(args.lng));
        } else {
          return textResult(
            'ERROR: provide one of: lat+lng, points, or bbox (see tool description).',
          );
        }
        p.set('limit', String(args.limit ?? 50));
        return textResult(await callApi(apiKey, `parcels/locate?${p.toString()}`, 'zornade_parcel_locate'));
      },
    },
    {
      name: 'zornade_parcel_search',
      description:
        'Search cadastral parcels by cadastral reference: municipality (fuzzy match), ' +
        'sheet number (foglio), parcel label, optional section. ' +
        'Returns matching parcels with FID, municipality, sheet, area and centroid.',
      inputSchema: z.object({
        comune: z.string().describe('Municipality name, required. Example: "Roma"'),
        foglio: z.string().optional().describe('Cadastral sheet number. Example: "481"'),
        label: z.string().optional().describe('Parcel label. Example: "A" or "123"'),
        sezione: z.string().optional().describe('Administrative section. Example: "A"'),
        limit: z.number().int().min(1).max(100).optional().describe('Max results, default 20'),
      }),
      handler: async (raw: Record<string, unknown>) => {
        const args = raw as {
          comune: string;
          foglio?: string;
          label?: string;
          sezione?: string;
          limit?: number;
        };
        const p = new URLSearchParams();
        p.set('comune', args.comune);
        if (args.foglio) p.set('foglio', args.foglio);
        if (args.label) p.set('label', args.label);
        if (args.sezione) p.set('sezione', args.sezione);
        p.set('limit', String(args.limit ?? 20));
        return textResult(await callApi(apiKey, `parcels/search?${p.toString()}`, 'zornade_parcel_search'));
      },
    },
    {
      name: 'zornade_admin_lists',
      description:
        'Italian administrative reference data: regions, provinces, or municipalities. ' +
        'Provinces can be filtered by region; municipalities by province or region.',
      inputSchema: z.object({
        type: z
          .enum(['regions', 'provinces', 'municipalities'])
          .describe('Which administrative list to return'),
        region: z.string().optional().describe('Filter by region name (provinces, municipalities)'),
        province: z.string().optional().describe('Filter by province name (municipalities)'),
      }),
      handler: async (raw: Record<string, unknown>) => {
        const args = raw as {
          type: 'regions' | 'provinces' | 'municipalities';
          region?: string;
          province?: string;
        };
        const p = new URLSearchParams();
        if (args.region) p.set('region', args.region);
        if (args.province) p.set('province', args.province);
        const qs = p.toString();
        return textResult(await callApi(apiKey, `admin/${args.type}${qs ? `?${qs}` : ''}`, 'zornade_admin_lists'));
      },
    },
  ];
}
