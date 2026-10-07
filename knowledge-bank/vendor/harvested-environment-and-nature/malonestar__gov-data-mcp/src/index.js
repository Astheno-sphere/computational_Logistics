#!/usr/bin/env node
/**
 * gov-data-mcp — MCP server exposing every published US government open-data
 * Actor in the bundled catalog. The count is deliberately NOT written down
 * here; it is read from src/catalog.json at runtime, because a number in a
 * comment rots the moment a batch ships and nothing fails when it does.
 *
 * Wiring only. All decision logic lives in src/tools.js (pure, offline-tested),
 * src/presets.js (vertical presets: --preset <name> / GOV_DATA_MCP_PRESET, pure)
 * and src/apify.js (fetch injected). A test asserts this file holds no logic
 * beyond dispatch.
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { createClient, ApifyError } from './apify.js';
import { indexCatalog, listTools, searchCatalog, describeTool, resolveCall, formatRunResult, META_TOOLS } from './tools.js';
import { parseCliArgs, resolvePreset, describePresets, PRESET_ENV } from './presets.js';

const here = dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(readFileSync(join(here, '..', 'package.json'), 'utf8'));
const catalog = JSON.parse(readFileSync(join(here, 'catalog.json'), 'utf8'));

// --preset <name> / GOV_DATA_MCP_PRESET scopes the server to one vertical.
// Nothing here decides anything: parsing and resolution are pure (presets.js)
// and an unknown or empty preset stops the process before the transport opens,
// so a client never connects to a server serving the wrong shelf.
const cli = parseCliArgs(process.argv.slice(2), process.env);
if (cli.listPresets) {
  process.stdout.write(JSON.stringify(describePresets(), null, 2) + '\n');
  process.exit(0);
}
if (cli.errors.length) {
  console.error(`[gov-data-mcp] ${cli.errors.join('; ')}. Known presets: ${describePresets().map(p => p.name).join(', ')}. Omit --preset (and ${PRESET_ENV}) for the full catalog.`);
  process.exit(2);
}
const chosen = resolvePreset(cli.presetName);
if (!chosen.ok) {
  console.error(`[gov-data-mcp] ${chosen.error}`);
  process.exit(2);
}
const index = indexCatalog(catalog, { preset: chosen.preset, presetName: chosen.name });

const identity = chosen.preset
  ? { name: chosen.preset.serverName, version: pkg.version, title: chosen.preset.title, description: chosen.preset.description, websiteUrl: 'https://apify.com/malonestar' }
  : { name: 'gov-data-mcp', version: pkg.version };

const server = new Server(
  identity,
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: listTools(index) }));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { name, arguments: args } = req.params;
  const text = (s, isError = false) => ({ content: [{ type: 'text', text: s }], isError });

  try {
    if (name === META_TOOLS.SEARCH) {
      const results = searchCatalog(index, args?.query, args?.limit ?? 10);
      if (results.length === 0) {
        return text(`No tool in this catalog matches "${args?.query}". The catalog covers ${index.actors.length} US government data sources; this is a catalog miss, not a statement about whether the data exists.`);
      }
      return text(JSON.stringify({ query: args?.query, matches: results.length, results }, null, 2));
    }

    if (name === META_TOOLS.DESCRIBE) {
      const d = describeTool(index, args?.tool);
      return text(JSON.stringify(d, null, 2), !d.ok);
    }

    const call = resolveCall(index, name, args);
    if (!call.ok) return text(call.error, true);

    const token = process.env.APIFY_TOKEN || process.env.APIFY_API_TOKEN;
    const client = createClient({ token });
    const result = await client.runActor(`${catalog.owner}/${call.slug}`, call.input, {
      maxItems: call.maxItems ?? 200,
    });
    const formatted = formatRunResult(call.slug, result);
    return text(formatted.text, formatted.isError);
  } catch (err) {
    if (err instanceof ApifyError) return text(`${err.message}`, true);
    return text(`gov-data-mcp failed to complete the call to "${name}": ${err.message}. No data was returned and no conclusion should be drawn about the underlying source.`, true);
  }
});

async function main() {
  if (index.missingFeatured.length) {
    // Loud on stderr, never on stdout — stdout is the MCP transport.
    console.error(`[gov-data-mcp] WARNING: featured tools missing from catalog: ${index.missingFeatured.join(', ')}`);
  }
  await server.connect(new StdioServerTransport());
  const scope = index.presetName ? ` [preset ${index.presetName}: ${index.actors.length} of ${index.catalogTotal}]` : '';
  console.error(`[${identity.name}] ready — ${index.actors.length} government data tools${scope} (catalog generated ${catalog.generatedAt})`);
}

main().catch(err => {
  console.error('[gov-data-mcp] fatal:', err);
  process.exit(1);
});
