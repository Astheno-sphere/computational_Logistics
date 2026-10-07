#!/usr/bin/env node
/**
 * Smoke tests for DealFlowPro MCP Server.
 *
 * Spawns the server with a dummy API key and sends JSON-RPC messages
 * over stdio to verify initialization and tool registration.
 */

import { spawn } from "child_process";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SERVER_PATH = join(__dirname, "index.js");

let passed = 0;
let failed = 0;

function assert(condition, msg) {
  if (condition) {
    console.log(`  PASS: ${msg}`);
    passed++;
  } else {
    console.error(`  FAIL: ${msg}`);
    failed++;
  }
}

function sendJsonRpc(proc, id, method, params = {}) {
  const msg = JSON.stringify({ jsonrpc: "2.0", id, method, params });
  proc.stdin.write(msg + "\n");
}

function parseResponses(data) {
  return data
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

async function runTests() {
  console.log("DealFlowPro MCP Server — smoke tests\n");

  const proc = spawn("node", [SERVER_PATH], {
    env: { ...process.env, DFP_API_KEY: "test_dummy_key" },
    stdio: ["pipe", "pipe", "pipe"],
  });

  let stdout = "";
  proc.stdout.on("data", (chunk) => {
    stdout += chunk.toString();
  });

  let stderr = "";
  proc.stderr.on("data", (chunk) => {
    stderr += chunk.toString();
  });

  // Send initialize request
  sendJsonRpc(proc, 0, "initialize", {
    protocolVersion: "2025-11-25",
    capabilities: {},
    clientInfo: { name: "test-runner", version: "1.0.0" },
  });

  // Wait for initialize response, then request tool list
  await new Promise((resolve) => setTimeout(resolve, 1500));

  sendJsonRpc(proc, 1, "tools/list", {});

  await new Promise((resolve) => setTimeout(resolve, 1000));

  // Parse responses
  const responses = parseResponses(stdout);

  // Test 1: Server responds to initialize
  const initResp = responses.find((r) => r.id === 0);
  assert(initResp != null, "Server responds to initialize");

  // Test 2: Protocol version returned
  assert(
    initResp?.result?.protocolVersion != null,
    "Returns protocol version: " + (initResp?.result?.protocolVersion ?? "missing")
  );

  // Test 3: Server name is DealFlowPro
  assert(
    initResp?.result?.serverInfo?.name === "DealFlowPro",
    "Server name is DealFlowPro"
  );

  // Test 4: Tools capability advertised
  assert(
    initResp?.result?.capabilities?.tools != null,
    "Advertises tools capability"
  );

  // Test 5: tools/list returns tools
  const toolsResp = responses.find((r) => r.id === 1);
  const tools = toolsResp?.result?.tools || [];
  assert(tools.length === 4, `Registers 4 tools (got ${tools.length})`);

  // Test 6-9: Each expected tool is present
  const expectedTools = ["analyze_deal", "score_deal", "reverse_calc", "market_data"];
  for (const name of expectedTools) {
    assert(
      tools.some((t) => t.name === name),
      `Tool "${name}" is registered`
    );
  }

  // Test 10: Each tool has inputSchema
  for (const tool of tools) {
    assert(
      tool.inputSchema?.type === "object",
      `Tool "${tool.name}" has valid inputSchema`
    );
  }

  // Clean up
  proc.kill();

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

runTests().catch((err) => {
  console.error("Test runner error:", err);
  process.exit(1);
});
