// ─────────────────────────────────────────────────────────────────────────────
// Zornade MCP server - Supabase Edge Function `mcp`
//
// Espone l'API v2 di Zornade come strumenti Model Context Protocol
// (streamable HTTP) per client AI: Claude, Cursor, VS Code Copilot, Cline, ecc.
// Pattern ufficiale Supabase con mcp-lite:
// https://supabase.com/docs/guides/functions/examples/mcp-server-mcp-lite
//
// Endpoint pubblico (via proxy Netlify mcp.zornade.com):
//   https://mcp.zornade.com/mcp
// Upstream diretto:
//   https://wupqwfqjfpwrapgnogjv.supabase.co/functions/v1/mcp/mcp
//
// Autenticazione: la chiave API Zornade (zrn_..., gratuita su
// https://app.zornade.com/api) va inviata in uno di questi modi:
//   - header  x-api-key: zrn_...
//   - header  Authorization: Bearer zrn_...
//   - query   ?api_key=zrn_...
// Il rate limit (10000 richieste/ora) e gli scope sono quelli della chiave.
// ─────────────────────────────────────────────────────────────────────────────

import { Hono, type Context } from 'npm:hono@4.6.14';
import { McpServer, StreamableHttpTransport } from 'npm:mcp-lite@0.8.2';
import { z } from 'npm:zod@4.1.12';
import { buildTools, extractApiKey, logMcpUsage } from './tools.ts';
import type { ToolTextResult } from './tools.ts';

const CORS: Record<string, string> = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers':
    'authorization, x-api-key, content-type, mcp-session-id, mcp-protocol-version, last-event-id, accept',
  'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
  'Access-Control-Expose-Headers': 'mcp-session-id',
};

function createMcp(apiKey: string | null): McpServer {
  const mcp = new McpServer({
    name: 'zornade',
    version: '1.0.0',
    schemaAdapter: (schema) => z.toJSONSchema(schema as z.ZodType),
  });

  for (const tool of buildTools(apiKey)) {
    mcp.tool(tool.name, {
      description: tool.description,
      inputSchema: tool.inputSchema,
      handler: tool.handler as (
        args: Record<string, unknown>,
      ) => Promise<ToolTextResult>,
    });
  }

  return mcp;
}

// ─── Routing (pattern Supabase: la funzione è montata su /mcp/*) ─────────────

const mcpApp = new Hono();

mcpApp.get('/', (c) =>
  c.json({
    name: 'Zornade MCP server',
    version: '1.0.0',
    description:
      'MCP (Model Context Protocol) server for Zornade API v2: Italian cadastral parcels, geocoding and administrative data.',
    mcp_endpoint: `${new URL(c.req.url).origin}/mcp`,
    authentication:
      'Send your free Zornade API key (zrn_...) via x-api-key header, Authorization: Bearer, or ?api_key= query parameter. Get one at https://app.zornade.com/api',
    documentation: 'https://api.zornade.com',
  }),
);

// Handler MCP condiviso: montato sia su /mcp (endpoint pubblico) sia su /
// (radice) cosi' che il container Docker risponda anche a chi prova la radice
// (es. check automatizzati tipo Glama). Su Supabase il platform inoltra solo
// richieste sotto /mcp, quindi la rotta / e' inerte in produzione.
async function mcpHandler(c: Context): Promise<Response> {
  // Log dell'evento initialize (clientInfo.name) per il monitoraggio in
  // Grafana. Il body viene letto su un clone: la richiesta originale resta
  // integra per il transport MCP.
  try {
    const clone = c.req.raw.clone();
    const body = (await clone.json()) as {
      method?: string;
      params?: { clientInfo?: { name?: string } };
    } | null;
    if (body?.method === 'initialize') {
      logMcpUsage({ tool: 'initialize', client: body.params?.clientInfo?.name ?? null });
    }
  } catch {
    // Body assente o non JSON (es. GET per SSE): nessun log.
  }
  // Per ogni richiesta costruiamo il server con la chiave estratta dagli
  // header: gli handler dei tool la chiudono nel proprio scope.
  const apiKey = extractApiKey(c.req.raw);
  const mcp = createMcp(apiKey);
  const transport = new StreamableHttpTransport();
  const httpHandler = transport.bind(mcp);
  const res = await httpHandler(c.req.raw);
  for (const [k, v] of Object.entries(CORS)) {
    res.headers.set(k, v);
  }
  return res;
}

mcpApp.options('/mcp', (c) => new Response(null, { status: 204, headers: CORS }));
mcpApp.all('/mcp', mcpHandler);
mcpApp.options('/', (c) => new Response(null, { status: 204, headers: CORS }));
mcpApp.all('/', mcpHandler);

const app = new Hono();
// Doppio mount: su Supabase il path effettivo e' /mcp/mcp (il platform include
// il prefisso della funzione), nel container Docker invece / e /mcp.
app.route('/', mcpApp);
app.route('/mcp', mcpApp);

// ZORNADE_LISTEN_PORTS (solo container/self-hosting): lista di porte separate
// da virgola su cui servire l'MCP. Utile per i check automatici che provano
// porte convenzionali (3000/8000/8080). Su Supabase la variabile non esiste e
// resta il comportamento platform default (Deno.serve senza opzioni).
const listenPorts = (Deno.env.get('ZORNADE_LISTEN_PORTS') ?? '')
  .split(',')
  .map((p) => Number(p.trim()))
  .filter((p) => Number.isInteger(p) && p > 0 && p < 65536);

if (listenPorts.length > 0) {
  for (const port of listenPorts) {
    Deno.serve({ port, hostname: '0.0.0.0' }, app.fetch);
  }
} else {
  Deno.serve(app.fetch);
}
