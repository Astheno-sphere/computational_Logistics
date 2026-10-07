#!/usr/bin/env node
import type { Logger } from "@geowirehq/provider-sdk";
import { buildServer } from "./app.js";
import { createGeoFromEnv } from "./geo.js";

const logger: Logger = {
  debug: () => {},
  info: (m, ...a) => console.error("[geowire:info]", m, ...a),
  warn: (m, ...a) => console.error("[geowire:warn]", m, ...a),
  error: (m, ...a) => console.error("[geowire:error]", m, ...a),
};

async function main(): Promise<void> {
  const port = Number(process.env.PORT ?? 4980);
  const host = process.env.HOST ?? "0.0.0.0";
  const apiKeys = process.env.GEOWIRE_API_KEYS?.split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const geo = createGeoFromEnv(logger);
  const app = await buildServer({ geo, apiKeys });
  await app.listen({ port, host });
  logger.info(`geowire-server on http://${host}:${port} (docs: /docs, mcp: /mcp)`);
}

main().catch((err) => {
  console.error("[geowire:fatal]", err);
  process.exit(1);
});
