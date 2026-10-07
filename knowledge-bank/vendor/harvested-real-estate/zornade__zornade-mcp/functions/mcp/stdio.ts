// ─────────────────────────────────────────────────────────────────────────────
// Zornade MCP - entrypoint stdio (container / check automatici Glama)
//
// Implementazione minimale del protocollo MCP su stdin/stdout: mcp-proxy (il
// wrapper usato dai check Glama) avvia questo file come processo figlio e parla
// JSON-RPC su stdio. Supporta initialize, ping, tools/list, tools/call e
// notifiche. Le definizioni dei tool sono condivise con index.ts via tools.ts.
// La chiave API (opzionale) si legge da ZORNADE_API_KEY.
// ─────────────────────────────────────────────────────────────────────────────

import { z } from 'npm:zod@4.1.12';
import { buildTools, logMcpUsage } from './tools.ts';

const apiKey = Deno.env.get('ZORNADE_API_KEY') ?? null;
const tools = buildTools(apiKey);

const encoder = new TextEncoder();
const decoder = new TextDecoder();

function send(msg: unknown): void {
  Deno.stdout.writeSync(encoder.encode(JSON.stringify(msg) + '\n'));
}

function reply(id: unknown, result: unknown): void {
  send({ jsonrpc: '2.0', id, result });
}

function replyError(id: unknown, code: number, message: string): void {
  send({ jsonrpc: '2.0', id, error: { code, message } });
}

async function handleRequest(msg: {
  id?: unknown;
  method?: string;
  params?: Record<string, unknown>;
}): Promise<void> {
  const id = msg.id;
  const method = msg.method ?? '';

  // Notifiche (initialize completato, ecc.): nessuna risposta attesa.
  if (id === undefined || id === null) return;

  switch (method) {
    case 'initialize': {
      const params = (msg.params ?? {}) as {
        protocolVersion?: string;
        clientInfo?: { name?: string };
      };
      logMcpUsage({ tool: 'initialize', client: params.clientInfo?.name ?? null });
      reply(id, {
        protocolVersion: params.protocolVersion ?? '2025-06-18',
        capabilities: { tools: { listChanged: false } },
        serverInfo: { name: 'zornade', version: '1.0.0' },
        instructions:
          'Zornade MCP server (stdio). Italian cadastral, geospatial and real estate data via the Zornade API v2.',
      });
      return;
    }
    case 'ping':
      reply(id, {});
      return;
    case 'tools/list':
      reply(id, {
        tools: tools.map((t) => ({
          name: t.name,
          description: t.description,
          inputSchema: z.toJSONSchema(t.inputSchema),
        })),
      });
      return;
    case 'tools/call': {
      const params = (msg.params ?? {}) as {
        name?: string;
        arguments?: Record<string, unknown>;
      };
      const tool = tools.find((t) => t.name === params.name);
      if (!tool) {
        replyError(id, -32602, `Unknown tool: ${String(params.name)}`);
        return;
      }
      try {
        const result = await tool.handler(params.arguments ?? {});
        reply(id, { ...result, isError: result.isError ?? false });
      } catch (e) {
        reply(id, {
          content: [{ type: 'text', text: `ERROR: ${(e as Error).message}` }],
          isError: true,
        });
      }
      return;
    }
    default:
      replyError(id, -32601, `Method not found: ${method}`);
  }
}

let buffer = '';

for await (const chunk of Deno.stdin.readable) {
  buffer += decoder.decode(chunk);
  let idx: number;
  while ((idx = buffer.indexOf('\n')) >= 0) {
    const line = buffer.slice(0, idx).trim();
    buffer = buffer.slice(idx + 1);
    if (!line) continue;
    let msg: unknown;
    try {
      msg = JSON.parse(line);
    } catch {
      continue;
    }
    if (typeof msg !== 'object' || msg === null) continue;
    await handleRequest(
      msg as { id?: unknown; method?: string; params?: Record<string, unknown> },
    );
  }
}
