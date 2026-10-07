#!/usr/bin/env node
// @thinairtelematics/geo — remote hosted MCP server shim.
// No local server process. Prints your mcp.json config block.
// Usage: npx @thinairtelematics/geo [--api-key <key>] [--transport sse]

const args = process.argv.slice(2);
const keyFlag = args.indexOf('--api-key');
const apiKey = keyFlag !== -1 ? args[keyFlag + 1] : null;
const useSSE = args.includes('--transport') && args[args.indexOf('--transport') + 1] === 'sse';

const url = useSSE ? 'https://geo.thinair.co/sse' : 'https://geo.thinair.co/mcp';

const keylessConfig = {
  mcpServers: {
    'thinair-geo': {
      type: 'url',
      url
    }
  }
};

const keyedConfig = {
  mcpServers: {
    'thinair-geo': {
      type: 'url',
      url,
      headers: {
        'x-api-key': apiKey
      }
    }
  }
};

const config = apiKey ? keyedConfig : keylessConfig;

console.log();
if (!apiKey) {
  console.log('Keyless config (OAuth 2.1 — recommended):');
  console.log('On first tool call your MCP client will open a browser tab to authorize.');
} else {
  console.log('API key config:');
}
console.log();
console.log(JSON.stringify(config, null, 2));
console.log();
console.log('Get a free API key at: https://geo.thinair.co/connect');
console.log('Docs:                  https://geo.thinair.co/docs/getting-started');
console.log();
