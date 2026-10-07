#!/usr/bin/env node
// Root entry shim — Glama's MCP runner invokes `node index.js` from /app.
// Delegate to the real ESM server under plugin/mcp-server/.
import("./plugin/mcp-server/index.mjs").catch((err) => {
  console.error(err);
  process.exit(1);
});
