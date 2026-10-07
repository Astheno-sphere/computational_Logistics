#!/usr/bin/env node

import { startStdioServer } from './server/transports/stdio.js';
import { startHttpServer } from './server/transports/http.js';
import { loadRuntimeConfig } from './config/runtime.js';
import { redactForLog } from './util/redact.js';

export const projectName = 'vessel-traffic-mcp';

export async function main(): Promise<void> {
  const config = loadRuntimeConfig();

  if (config.transport === 'stdio') {
    await startStdioServer();
    return;
  }

  await startHttpServer(config.http);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`vessel-traffic-mcp failed to start: ${redactForLog(message)}`);
    process.exitCode = 1;
  });
}
