#!/usr/bin/env node
/**
 * Swath MCP server (spec §3.5) — exposes the Swath V1 API as agent tools.
 *
 * Env:
 *   SWATH_API_URL  base URL of the API (default http://localhost:8787)
 *   SWATH_API_KEY  API key; without one, most tools return the signup hint
 */
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

const BASE = (process.env.SWATH_API_URL ?? 'https://swathapi.com').replace(/\/$/, '');
const KEY = process.env.SWATH_API_KEY ?? '';

async function api(path: string, init?: RequestInit): Promise<unknown> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.headers ?? {}),
      authorization: `Bearer ${KEY}`,
      'content-type': 'application/json',
    },
    signal: AbortSignal.timeout(60_000),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = (body as { error?: { message?: string } }).error?.message ?? `HTTP ${res.status}`;
    throw new Error(
      res.status === 401
        ? `${msg}. Set SWATH_API_KEY — get one free: POST ${BASE}/v1/signup {"email":"you@example.com"}`
        : msg,
    );
  }
  return body;
}

function jsonResult(data: unknown) {
  return { content: [{ type: 'text' as const, text: JSON.stringify(data, null, 2) }] };
}

const server = new McpServer({ name: 'swath', version: '0.1.0' });

server.tool(
  'find_storms',
  'List radar-verified hail/wind storm events (hail measured by NOAA radar, wind from measured NWS gust and damage reports — never forecasts). ' +
    'Returns storm ids usable with get_swath_report and show_swath_map.',
  {
    since: z.string().optional().describe('ISO timestamp or date; e.g. 2026-07-18'),
    bbox: z.string().optional().describe('west,south,east,north in lon/lat, e.g. -97.5,32.5,-96.4,33.3'),
    type: z.enum(['hail', 'wind']).optional(),
    limit: z.number().int().min(1).max(500).optional(),
  },
  { title: 'Find storms', readOnlyHint: true },
  async (args) => {
    const q = new URLSearchParams();
    if (args.since) q.set('since', args.since);
    if (args.bbox) q.set('bbox', args.bbox);
    if (args.type) q.set('type', args.type);
    if (args.limit) q.set('limit', String(args.limit));
    return jsonResult(await api(`/v1/storms?${q}`));
  },
);

server.tool(
  'get_swath_report',
  '★ The Swath Report: every property inside a storm swath, each scored with the hail size ' +
    'measured at that location (exposure.hail_in, exposure.score 0-1). Bills 1 credit per property ' +
    'returned +25/fresh-fetched record (10 min); preview with get_report_quote.',
  {
    storm_id: z.string().describe('Storm id (sw_...) or swath id from find_storms'),
    roof_age_min: z.number().int().optional(),
    roof_material: z.string().optional(),
    owner_occupied: z.boolean().optional(),
    year_built_before: z.number().int().optional(),
    year_built_after: z.number().int().optional(),
    value_min: z.number().optional(),
    value_max: z.number().optional(),
    min_exposure_score: z.number().min(0).max(1).optional(),
    limit: z.number().int().min(1).max(1000).optional(),
    offset: z.number().int().min(0).optional(),
  },
  { title: 'Swath report (affected properties)', readOnlyHint: true },
  async ({ storm_id, ...filters }) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) if (v !== undefined) q.set(k, String(v));
    return jsonResult(await api(`/v1/swaths/${encodeURIComponent(storm_id)}/properties?${q}`));
  },
);

server.tool(
  'get_report_quote',
  'Cost preview for get_swath_report (1 credit): counts cached properties matching the filters ' +
    'without returning rows, plus a clearly-labeled estimate of fresh-fetchable records. ' +
    'Billing always uses actual counts. Use before pulling large reports.',
  {
    storm_id: z.string().describe('Storm id (sw_...) or swath id from find_storms'),
    roof_age_min: z.number().int().optional(),
    roof_material: z.string().optional(),
    owner_occupied: z.boolean().optional(),
    year_built_before: z.number().int().optional(),
    year_built_after: z.number().int().optional(),
    value_min: z.number().optional(),
    value_max: z.number().optional(),
    min_exposure_score: z.number().min(0).max(1).optional(),
  },
  { title: 'Swath report cost quote', readOnlyHint: true },
  async ({ storm_id, ...filters }) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) if (v !== undefined) q.set(k, String(v));
    return jsonResult(await api(`/v1/swaths/${encodeURIComponent(storm_id)}/properties/quote?${q}`));
  },
);

server.tool(
  'email_report',
  'Email a swath report summary (max hail/wind, swath area, county, affected-property count, storm link) ' +
    'to your account email — the address your API key was signed up with; no other recipients possible. ' +
    'Summary bills 1 credit (like get_report_quote); pass limit to also include the top N properties by ' +
    'exposure, billed like get_swath_report (1 credit/property + fresh surcharges, 10-credit minimum).',
  {
    storm_id: z.string().describe('Storm id (sw_...) or swath id from find_storms'),
    limit: z.number().int().min(1).max(50).optional().describe('include the top N properties in the email (billed like get_swath_report); omit for a 1-credit summary'),
    roof_age_min: z.number().int().optional(),
    roof_material: z.string().optional(),
    owner_occupied: z.boolean().optional(),
    year_built_before: z.number().int().optional(),
    year_built_after: z.number().int().optional(),
    value_min: z.number().optional(),
    value_max: z.number().optional(),
    min_exposure_score: z.number().min(0).max(1).optional(),
  },
  { title: 'Email swath report', readOnlyHint: false, destructiveHint: false },
  async ({ storm_id, ...filters }) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) if (v !== undefined) q.set(k, String(v));
    return jsonResult(await api(`/v1/swaths/${encodeURIComponent(storm_id)}/email-report?${q}`, { method: 'POST' }));
  },
);

server.tool(
  'lookup_property',
  'Full property record for one address (or lat/lng, or parcel id): year built, sqft, roof age ' +
    'and how it was derived, owner-occupancy, assessed value. Costs 2 credits.',
  {
    address: z.string().optional(),
    lat: z.number().optional(),
    lng: z.number().optional(),
    parcel_id: z.string().optional(),
  },
  { title: 'Property lookup', readOnlyHint: true },
  async (args) => {
    const q = new URLSearchParams();
    if (args.address) q.set('address', args.address);
    if (args.lat !== undefined && args.lng !== undefined) {
      q.set('lat', String(args.lat));
      q.set('lng', String(args.lng));
    }
    if (args.parcel_id) q.set('parcel_id', args.parcel_id);
    return jsonResult(await api(`/v1/property?${q}`));
  },
);

server.tool(
  'create_monitor',
  'Watch a coverage area. Get an email at your account address and/or a signed webhook when a ' +
    'radar-verified storm crosses it. Provide email_alerts: true and/or webhook_url (at least one). ' +
    'With webhook_url, the response includes webhook_secret ONCE — store it.',
  {
    name: z.string().optional(),
    bbox: z.array(z.number()).length(4).describe('[west, south, east, north]'),
    hail_min_in: z.number().min(0.5).max(5).optional().describe('hail threshold in inches, default 1.0'),
    webhook_url: z.string().url().optional().describe('optional endpoint for signed storm.verified POSTs'),
    email_alerts: z.boolean().optional().describe('email storm alerts to the account owner\'s address (no other recipients possible)'),
  },
  { title: 'Create storm monitor', readOnlyHint: false, destructiveHint: false },
  async (args) => jsonResult(await api('/v1/monitors', { method: 'POST', body: JSON.stringify(args) })),
);

server.tool('list_monitors', 'List your registered coverage monitors.', {}, { title: 'List monitors', readOnlyHint: true }, async () =>
  jsonResult(await api('/v1/monitors')),
);

server.tool(
  'show_swath_map',
  "A storm swath's polygon as GeoJSON (render it on any map) plus severity stats and a viewer URL.",
  { storm_id: z.string().describe('Storm id (sw_...) or swath id') },
  { title: 'Swath map', readOnlyHint: true },
  async ({ storm_id }) => {
    const [meta, geometry] = await Promise.all([
      api(`/v1/swaths/${encodeURIComponent(storm_id)}`),
      api(`/v1/swaths/${encodeURIComponent(storm_id)}/geometry`),
    ]);
    return jsonResult({ ...(meta as object), geojson: geometry, map_url: `${BASE}/map` });
  },
);

server.tool('get_usage', 'Your API plan, credits used this month, and rate limit.', {}, { title: 'Usage & credits', readOnlyHint: true }, async () =>
  jsonResult(await api('/v1/usage')),
);

const transport = new StdioServerTransport();
await server.connect(transport);
console.error(`swath-mcp connected (api: ${BASE}, key: ${KEY ? 'set' : 'MISSING'})`);
