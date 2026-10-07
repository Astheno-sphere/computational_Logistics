import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { DeliveryClient } from "../dist/client.js";
import { registerExpressTools } from "../dist/tools/express.js";
import { registerPlatformTools } from "../dist/tools/platform.js";
import { registerRawTool } from "../dist/tools/raw.js";

const ALL_TOOLS = [
  "express_accept_claim",
  "express_cancel_claim",
  "express_cancel_info",
  "express_check_price",
  "express_create_claim",
  "express_get_claim",
  "express_performer_position",
  "express_search_claims",
  "express_tracking_links",
  "platform_cancel_request",
  "platform_confirm_offer",
  "platform_create_offers",
  "platform_get_request",
  "platform_list_pickup_points",
  "platform_request_history",
  "raw_request",
];

test("dist client rejects foreign-origin paths before sending the Bearer token", async () => {
  let called = false;
  globalThis.fetch = async () => {
    called = true;
    return new Response("{}", { status: 200 });
  };

  const client = new DeliveryClient({
    expressToken: "SECRET",
    platformToken: "SECRET",
    expressBase: "https://b2b.taxi.yandex.net",
    platformBase: "https://b2b-authproxy.taxi.yandex.net",
    lang: "ru",
    timeoutMs: 1000,
    maxRetries: 0,
  });

  await assert.rejects(
    () => client.request("express", "POST", "https://example.invalid/steal", { body: {} }),
    /foreign origin/,
  );
  await assert.rejects(
    () => client.request("platform", "GET", "https://example.invalid/steal"),
    /foreign origin/,
  );
  assert.equal(called, false);
});

test("dist registers the full tool set", () => {
  const names = [];
  const server = {
    registerTool(name) {
      names.push(name);
    },
  };
  const client = {};

  registerExpressTools(server, client);
  registerPlatformTools(server, client);
  registerRawTool(server, client);

  assert.deepEqual(names.sort(), ALL_TOOLS);
});

/** process.env without any YANDEX_DELIVERY_* variable, telemetry off — the suite stays offline. */
function bareEnv(extra = {}) {
  const env = Object.fromEntries(
    Object.entries(process.env).filter(
      ([key, value]) => value !== undefined && !key.startsWith("YANDEX_DELIVERY_"),
    ),
  );
  return { ...env, ASKADS_TELEMETRY: "0", ...extra };
}

test("dist bin completes an MCP handshake over stdio and lists every tool", async () => {
  const { Client } = await import("@modelcontextprotocol/sdk/client/index.js");
  const { StdioClientTransport } = await import("@modelcontextprotocol/sdk/client/stdio.js");

  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [fileURLToPath(new URL("../dist/index.js", import.meta.url))],
    env: bareEnv({ YANDEX_DELIVERY_TOKEN: "smoke-test-token" }),
  });
  const client = new Client({ name: "dist-smoke", version: "0.0.0" });
  await client.connect(transport);
  try {
    const res = await client.listTools();
    assert.deepEqual(res.tools.map((t) => t.name).sort(), ALL_TOOLS);
    // The handshake reported the real server identity.
    const server = client.getServerVersion();
    assert.equal(server?.name, "mcp-yandex-dostavka");
    // ...and the prose the calling model reads before picking a tool.
    const instructions = client.getInstructions();
    assert.equal(typeof instructions, "string");
    assert.ok(instructions.length > 0, "initialize result must carry non-empty instructions");
    assert.ok(!instructions.startsWith("ВНИМАНИЕ"), "a configured start must not carry the unconfigured prefix");
  } finally {
    await client.close();
  }
});

/**
 * The degraded-start contract: without any token the binary used to exit(1)
 * before the handshake, leaving the client a dead server and no reason. It must
 * now start, list every tool, open the instructions with the fix, and answer a
 * tool call with the actionable error — offline: the CredentialsError fires
 * before any fetch, so this test never touches the network.
 */
test("dist bin starts without tokens: handshake, tool list, actionable call error", async () => {
  const { Client } = await import("@modelcontextprotocol/sdk/client/index.js");
  const { StdioClientTransport } = await import("@modelcontextprotocol/sdk/client/stdio.js");

  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [fileURLToPath(new URL("../dist/index.js", import.meta.url))],
    env: bareEnv(),
    stderr: "ignore",
  });
  const client = new Client({ name: "dist-smoke-unconfigured", version: "0.0.0" });
  await client.connect(transport);
  try {
    // The model must read the fix before it picks a tool.
    const instructions = client.getInstructions() ?? "";
    assert.match(instructions, /ВНИМАНИЕ/, "instructions must open with the unconfigured prefix");
    assert.match(instructions, /YANDEX_DELIVERY_TOKEN/, "and name the variable to set");
    assert.match(instructions, /перезапустить сервер/, "and say the server needs a restart");

    const { tools } = await client.listTools();
    assert.deepEqual(tools.map((t) => t.name).sort(), ALL_TOOLS);

    // A tool call fails with the exact historical message instead of killing the server.
    const result = await client.callTool({ name: "express_search_claims", arguments: {} });
    assert.equal(result.isError, true, "the call must fail, not the connection");
    const text = result.content.map((c) => c.text ?? "").join(" ");
    assert.match(
      text,
      /YANDEX_DELIVERY_TOKEN is required \(Bearer token from dostavka\.yandex\.ru → «Интеграции» → «Получить токен»\)\./,
      "the error must carry the historical startup text verbatim",
    );
    assert.match(text, /restart the server/, "and the restart hint");
  } finally {
    await client.close();
  }
});

test("dist bin with only a platform token serves platform and rejects express by name", async () => {
  const { Client } = await import("@modelcontextprotocol/sdk/client/index.js");
  const { StdioClientTransport } = await import("@modelcontextprotocol/sdk/client/stdio.js");

  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [fileURLToPath(new URL("../dist/index.js", import.meta.url))],
    env: bareEnv({ YANDEX_DELIVERY_PLATFORM_TOKEN: "smoke-platform-token" }),
    stderr: "ignore",
  });
  const client = new Client({ name: "dist-smoke-half-configured", version: "0.0.0" });
  await client.connect(transport);
  try {
    // The prefix is per contour: it must point at the express token and not
    // talk the model out of using the configured platform contour.
    const instructions = client.getInstructions() ?? "";
    assert.match(instructions, /YANDEX_DELIVERY_EXPRESS_TOKEN/, "instructions must name the express override");
    assert.match(instructions, /платформенный контур настроен/, "and say the platform contour works");

    // An express call fails offline (the CredentialsError fires before fetch)
    // with the express-contour text, not the shared-token one.
    const result = await client.callTool({ name: "express_search_claims", arguments: {} });
    assert.equal(result.isError, true);
    const text = result.content.map((c) => c.text ?? "").join(" ");
    assert.match(
      text,
      /Express-contour token is missing: set YANDEX_DELIVERY_TOKEN \(shared\) or YANDEX_DELIVERY_EXPRESS_TOKEN\./,
      "the error must carry the express-contour startup text verbatim",
    );
  } finally {
    await client.close();
  }
});
