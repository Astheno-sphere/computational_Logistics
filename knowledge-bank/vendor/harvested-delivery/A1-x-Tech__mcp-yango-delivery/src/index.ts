#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { DeliveryClient } from "./client.js";
import { ConfigError, DEFAULT_BASE, loadConfig } from "./config.js";
import { instrumentToolCalls, Telemetry } from "./telemetry.js";
import type { DeliveryConfig } from "./types.js";
import { registerClaimsTools } from "./tools/claims.js";
import { registerTrackingTools } from "./tools/tracking.js";
import { registerRawTool } from "./tools/raw.js";

/**
 * Prose handed to the calling model in the `initialize` result, before it sees a
 * single tool. It carries what the per-tool descriptions cannot: which contour of
 * the API this is (and which endpoints therefore do not exist), that every call
 * hits production with no sandbox, and the failure modes that read as something
 * else (a reset token, an unretried write, a claim that is simply not active yet).
 */
const INSTRUCTIONS =
  "Yango Delivery is the international brand of Yandex Delivery, and this server speaks only the " +
  "express (claims) contour of its B2B API: same-day, on-demand courier runs. The Russia-only " +
  "offers/calculate method and the platform contour are absent: no pickup-point or " +
  "next-day-delivery tools here, and every call is scoped to the one cabinet behind the token. Rate " +
  "limits are unpublished: 429 is retried with backoff automatically, but a timeout or 5xx on " +
  "accept/cancel is never replayed — re-read with get_claim to see whether the write landed rather " +
  "than repeating it. The token never expires, so 401/403 means a wrong token or one reset by a " +
  "cabinet password change, not a bad request; a 409 from the tracking tools is about the claim's " +
  "state (not active, no courier or links yet), and a wrong claim_id gives 404. Everything hits " +
  "production and there is no sandbox: an accepted claim dispatches a real courier and is billed, " +
  "and cancelling one can be paid, so confirm with the user before accept_claim, cancel_claim, " +
  "create_claim with auto_accept=true, or a state-changing raw_request.";

/**
 * Prepended to INSTRUCTIONS when the token is missing. The model reads this
 * before it picks a tool, so an unconfigured session opens with the fix rather
 * than with a failed call. There is no in-chat login here: the token comes
 * only from the environment, so the fix is an operator action + restart.
 */
const UNCONFIGURED_PREFIX =
  "ATTENTION: Yango Delivery is not connected yet — the YANGO_DELIVERY_TOKEN environment variable " +
  "is not set, so every tool call will fail. The operator must set YANGO_DELIVERY_TOKEN (OAuth " +
  'token from the delivery cabinet, Integration tab -> "Get token") in the MCP client\'s server ' +
  "config and restart this server — the variable is read only at startup. ";

/** Reads the package version so the server reports its real version to MCP clients. */
function readVersion(): string {
  try {
    const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
    return typeof pkg.version === "string" ? pkg.version : "0.0.0";
  } catch {
    return "0.0.0";
  }
}

/**
 * Loads the config without dying on a bad value. A server that exits here never
 * completes the MCP handshake, so the user sees a dead server and no reason —
 * instead the problem is carried into the session, where the model can read it
 * and relay it. (A missing token is not an error at all — loadConfig leaves the
 * field undefined; today it has no malformed-value checks either, so the catch
 * guards future ones.)
 */
function loadConfigOrDegraded(telemetry: Telemetry): {
  config: DeliveryConfig;
  problem?: ConfigError;
} {
  try {
    return { config: loadConfig() };
  } catch (err) {
    if (!(err instanceof ConfigError)) throw err;
    console.error(`Error: ${err.message}`);
    // Fire-and-forget now that the process survives: the historical
    // `startup_failed` funnel stays comparable, but nothing blocks startup.
    telemetry.send("startup_failed", { reason: err.reason });
    return {
      config: {
        baseUrl: process.env.YANGO_DELIVERY_BASE_URL || DEFAULT_BASE,
        lang: process.env.YANGO_DELIVERY_LANG || "en",
      },
      problem: err,
    };
  }
}

async function main(): Promise<void> {
  // Anonymous usage pings (ids/names/versions only, never data or arguments);
  // opt out with ASKADS_TELEMETRY=0. Built before the config so a config
  // problem can be reported; wired to the server before tools register.
  const telemetry = new Telemetry(readVersion());
  const { config, problem } = loadConfigOrDegraded(telemetry);
  const client = new DeliveryClient(config);

  // Decided once, at startup: the token comes only from the environment, so
  // "restart after setting the variable" is the accurate advice to give.
  const connected = Boolean(config.token);

  const server = new McpServer(
    {
      name: "mcp-yango-delivery",
      version: readVersion(),
    },
    // Surfaces in the initialize result, so the model reads it before its first call.
    {
      instructions: connected
        ? INSTRUCTIONS
        : UNCONFIGURED_PREFIX + (problem ? `Configuration problem: ${problem.message} ` : "") + INSTRUCTIONS,
    },
  );

  instrumentToolCalls(server, telemetry);
  server.server.oninitialized = () => {
    telemetry.setClientInfo(server.server.getClientVersion());
    // Split on purpose: `server_start` keeps meaning "a usable install started",
    // so the unconfigured case gets its own event instead of inflating that
    // number. The reason vocabulary is the historical closed set.
    if (connected) telemetry.send("server_start");
    else telemetry.send("unconfigured_start", { reason: problem?.reason ?? "missing_token" });
  };

  registerClaimsTools(server, client);
  registerTrackingTools(server, client);
  registerRawTool(server, client);

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error(
    `mcp-yango-delivery running on stdio${
      connected ? "" : " (YANGO_DELIVERY_TOKEN is not set — set the variable and restart)"
    }`,
  );
}

main().catch((err) => {
  console.error("Fatal error starting mcp-yango-delivery:", err);
  process.exit(1);
});
