#!/usr/bin/env node

/**
 * discava MCP Server (standalone)
 *
 * Search for local businesses worldwide via the discava API.
 * 49 countries, 8 languages, millions of businesses.
 *
 * Prerequisites:
 *   npm install @modelcontextprotocol/sdk zod
 *
 * Usage:
 *   npx tsx server.ts
 *
 * Configure in Claude Desktop (~/.claude/claude_desktop_config.json):
 *   {
 *     "mcpServers": {
 *       "discava": {
 *         "command": "npx",
 *         "args": ["tsx", "/path/to/server.ts"]
 *       }
 *     }
 *   }
 *
 * Or use the remote endpoint instead (no download needed):
 *   https://discava.ai/api/mcp
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

const API_BASE = 'https://discava.ai/api/v1';

async function api(path: string, options?: RequestInit): Promise<unknown> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

function jsonContent(data: unknown) {
  return { content: [{ type: 'text' as const, text: JSON.stringify(data, null, 2) }] };
}

const server = new McpServer({ name: 'discava', version: '1.1.0' });

server.tool(
  'search_businesses',
  'Search for local businesses. Returns name, category, city, country, logo_url, available_details (what data exists), and scores. Check available_details to see what is available, then call get_business for full details.',
  {
    query: z.string().optional().describe('Search query (e.g. "plumber", "Zahnarzt", "Italian restaurant")'),
    city: z.string().optional().describe('City name (e.g. "Hamburg", "Wien", "New York")'),
    country: z.string().describe('ISO country code (e.g. "DE", "AT", "CH", "US"). Required.'),
    category: z.string().optional().describe('Category slug (e.g. "plumber", "restaurant", "dentist")'),
    limit: z.number().optional().default(10).describe('Number of results (1-50, default 10)'),
    page: z.number().optional().default(1).describe('Page number'),
    min_confidence: z.number().optional().describe('Min confidence score 0-100'),
    lang: z.string().optional().default('en').describe('Language for labels: "de" or "en"'),
    lat: z.number().optional().describe('Latitude for distance'),
    lon: z.number().optional().describe('Longitude for distance'),
    format: z.enum(['json', 'html']).optional().default('json').describe('Response format: "json" (default) or "html" for interactive cards'),
  },
  async ({ query, city, country, category, limit, page, min_confidence, lang, lat, lon, format }) => {
    const params = new URLSearchParams({ country });
    if (query) params.set('q', query);
    if (city) params.set('city', city);
    if (category) params.set('category', category);
    if (limit) params.set('limit', String(limit));
    if (page) params.set('page', String(page));
    if (min_confidence) params.set('min_confidence', String(min_confidence));
    if (lang) params.set('lang', lang);
    if (lat !== undefined) params.set('lat', String(lat));
    if (lon !== undefined) params.set('lon', String(lon));
    if (format && format !== 'json') params.set('format', format);
    if (format === 'html') {
      const res = await fetch(`${API_BASE}/search?${params}`);
      return { content: [{ type: 'text' as const, text: await res.text() }] };
    }
    return jsonContent(await api(`/search?${params}`));
  }
);

server.tool(
  'get_business',
  'Get full details for one or more businesses: address, phone, website, opening hours, services, payment methods, social links, logo, business image, coordinates. Pass comma-separated IDs for batch.',
  {
    id: z.string().describe('One or more business IDs, comma-separated for batch (e.g. "id1,id2,id3")'),
    format: z.enum(['json', 'html']).optional().default('json').describe('Response format: "json" (default) or "html" for interactive cards'),
  },
  async ({ id, format }) => {
    if (format === 'html') {
      const res = await fetch(`${API_BASE}/business/${id}?format=html`);
      return { content: [{ type: 'text' as const, text: await res.text() }] };
    }
    return jsonContent(await api(`/business/${id}`));
  }
);

server.tool(
  'send_feedback',
  'Report data quality issues for a business.',
  {
    business_id: z.string().describe('Business ID'),
    type: z.enum(['POSITIVE', 'NEGATIVE', 'NOT_FOUND', 'PHONE_INVALID', 'WEB_INVALID', 'HOURS_WRONG', 'DUPLICATE']).describe('Feedback type'),
    comment: z.string().optional().describe('Description of the issue'),
  },
  async ({ business_id, type, comment }) => {
    return jsonContent(await api('/feedback', {
      method: 'POST',
      body: JSON.stringify({ business_id, type, comment }),
    }));
  }
);

server.tool(
  'get_rankings',
  'Get top businesses by demand score.',
  {
    country: z.string().describe('ISO country code (required)'),
    category: z.string().optional().describe('Category slug or name'),
    city: z.string().optional().describe('City name'),
    limit: z.number().optional().default(10).describe('Results (1-20)'),
    lang: z.string().optional().default('en').describe('Language for labels'),
  },
  async ({ country, category, city, limit, lang }) => {
    const params = new URLSearchParams({ country });
    if (category) params.set('category', category);
    if (city) params.set('city', city);
    if (limit) params.set('limit', String(limit));
    if (lang) params.set('lang', lang);
    return jsonContent(await api(`/ranking?${params}`));
  }
);

server.tool(
  'suggest',
  'Autocomplete for cities or categories/business names.',
  {
    query: z.string().describe('Search text (min 2 chars)'),
    type: z.enum(['city', 'query']).optional().default('query').describe('"city" or "query"'),
    country: z.string().optional().describe('ISO country code to filter'),
    limit: z.number().optional().default(10).describe('Max suggestions'),
  },
  async ({ query, type, country, limit }) => {
    const params = new URLSearchParams({ q: query, type });
    if (country) params.set('country', country);
    if (limit) params.set('limit', String(limit));
    return jsonContent(await api(`/suggest?${params}`));
  }
);

server.tool(
  'health_check',
  'Check if the discava API is online.',
  {},
  async () => jsonContent(await api('/health'))
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error('MCP server error:', err);
  process.exit(1);
});
